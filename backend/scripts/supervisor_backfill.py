"""Populate and verify supervisor coverage. Idempotent, resumable, reversible.

This is the operation that makes the coverage invariant true, and it is the only
supported way to populate coverage. It is deliberately separate from application
startup: production must not migrate or seed on the request path, because
``create_all`` plus DDL takes ACCESS EXCLUSIVE locks with no statement timeout and
has previously answered 503 indefinitely on a cold start (see app/main.py).

Two universes matter and they are not the same set:

* the **CATALOGUE universe** — everything ``public_visibility_conditions()``
  permits to be shown. This is the population the invariant is stated over, and
  it is the same population Count Intelligence's catalogue total describes.
* **every row**, archived included. Coverage is what was searched, not what is
  currently offered, so archived records keep their coverage row. A coverage row
  is not a publication decision: the public API applies the visibility predicate
  independently, so holding a row cannot make a hidden scholarship readable.

Usage::

    python supervisor_backfill.py --report-only          # measure, write nothing
    python supervisor_backfill.py --coverage-only        # create missing rows
    python supervisor_backfill.py --discover --limit 10  # opt-in outbound crawl
    python supervisor_backfill.py --rollback-coverage    # remove only the rows

Discovery is opt-in and off by default. It makes outbound requests to
universities, and the person who runs it should decide when and how much of that
to spend.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_engine, get_session_factory, init_database  # noqa: E402
from app.models import Scholarship  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorAvailability,
    ProfessorProfile,
    ScholarshipOfficialContact,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
)
from app.services.supervisor_coverage import (  # noqa: E402
    backfill_coverage,
    coverage_invariant_report,
    supervisor_universe_report,
)
from app.services.supervisor_status import (  # noqa: E402
    AUTHORITATIVE_SOURCE_TYPES,
    PUBLIC_RELATIONSHIP_STATUSES,
)

logger = logging.getLogger("supervisor_backfill")

#: Bounded per iteration. A very large catalogue is finished by repeated runs, and
#: no single transaction stays open long enough to upset a pooled Neon connection.
DEFAULT_BATCH_SIZE = 200


def _configure_logging() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def ensure_coverage(session: Session, batch_size: int, include_archived: bool) -> int:
    """Create coverage rows until none are missing. Returns how many were created."""
    created_total = 0
    while True:
        result = backfill_coverage(
            session, batch_size=batch_size, include_archived=include_archived
        )
        created_total += result.created
        if result.created == 0:
            break
        logger.info(
            "coverage: created=%s scanned=%s total=%s",
            result.created,
            result.scanned,
            result.total_scholarships,
        )
    return created_total


def rollback_coverage(session: Session) -> int:
    """Remove supervisor coverage rows without touching anything else.

    The reverse operation, and deliberately narrow: it deletes coverage only. It
    does not touch professors, links, evidence or outreach, because those are
    either verified public facts or a student's private history. Rollback is here
    so that enabling the feature in production is reversible without a restore.
    """
    count = session.query(ScholarshipSupervisorCoverage).delete()
    session.commit()
    logger.warning("removed %s coverage row(s); professor data left intact", count)
    return count


def _contacts_table_present(session: Session) -> bool:
    """Return whether this database has the contact table yet.

    The schema arrives by an out-of-band migration, so a report against a
    deployment that predates it must still produce numbers rather than a
    ProgrammingError. Reported as absent rather than as zero, because "the table
    is not there" and "the table is empty" are different facts.
    """
    from sqlalchemy import inspect

    return inspect(session.get_bind()).has_table("scholarship_official_contacts")


def data_quality_report(session: Session) -> dict:
    """Measure everything that would make a published claim false.

    Every number is read from the database at the moment it is called. None is
    estimated, and a failure is reported as a failure rather than rounded into an
    acceptable-looking total.
    """
    invariant = coverage_invariant_report(session)
    universe = supervisor_universe_report(session)

    verified_emails = session.execute(
        select(func.count(ProfessorProfile.id)).where(
            ProfessorProfile.official_email_verified.is_(True)
        )
    ).scalar_one()
    # An address that is present but unconfirmed is dead weight at best and a
    # pending liability at worst, so it is counted rather than ignored.
    unverified_emails_stored = session.execute(
        select(func.count(ProfessorProfile.id)).where(
            ProfessorProfile.official_email.isnot(None),
            ProfessorProfile.official_email_verified.is_(False),
        )
    ).scalar_one()
    total_links = session.execute(
        select(func.count(ScholarshipProfessorLink.id))
    ).scalar_one()
    verified_links = session.execute(
        select(func.count(ScholarshipProfessorLink.id)).where(
            ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES)
        )
    ).scalar_one()
    links_without_source = session.execute(
        select(func.count(ScholarshipProfessorLink.id)).where(
            (ScholarshipProfessorLink.evidence_source_url.is_(None))
            | (ScholarshipProfessorLink.evidence_source_url == "")
        )
    ).scalar_one()
    # A public relationship resting on a secondary aggregator would be a published
    # claim on a non-authoritative page. Must be zero.
    links_on_secondary = session.execute(
        select(func.count(ScholarshipProfessorLink.id)).where(
            ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
            ScholarshipProfessorLink.evidence_source_type.not_in(AUTHORITATIVE_SOURCE_TYPES),
        )
    ).scalar_one()
    availability_states = {
        state: count
        for state, count in session.execute(
            select(ProfessorAvailability.state, func.count(ProfessorAvailability.id)).group_by(
                ProfessorAvailability.state
            )
        ).all()
    }
    availability_without_source = session.execute(
        select(func.count(ProfessorAvailability.id)).where(
            (ProfessorAvailability.source_url.is_(None)) | (ProfessorAvailability.source_url == "")
        )
    ).scalar_one()
    duplicate_profiles = session.execute(
        select(func.count(ProfessorProfile.id)).where(
            ProfessorProfile.official_profile_url.in_(
                select(ProfessorProfile.official_profile_url)
                .group_by(ProfessorProfile.official_profile_url)
                .having(func.count(ProfessorProfile.id) > 1)
            )
        )
    ).scalar_one()
    orphan_links = session.execute(
        select(func.count(ScholarshipProfessorLink.id)).where(
            ScholarshipProfessorLink.scholarship_id.not_in(select(Scholarship.id))
        )
    ).scalar_one()

    # Official contacts, measured against the same two tests the professor side
    # answers to: a source behind every claim, and an email published only when
    # it was actually read off one. A contact is an office, so there is no
    # "verified contact" count to inflate these by.
    contacts_present = _contacts_table_present(session)
    total_contacts = 0
    contacts_without_evidence = 0
    contacts_on_non_authoritative_source = 0
    orphan_contacts = 0
    contact_emails_verified = 0
    contact_emails_stored_unverified = 0
    if contacts_present:
        total_contacts = session.execute(
            select(func.count(ScholarshipOfficialContact.id))
        ).scalar_one()
        contacts_without_evidence = session.execute(
            select(func.count(ScholarshipOfficialContact.id)).where(
                (ScholarshipOfficialContact.evidence_source_url.is_(None))
                | (ScholarshipOfficialContact.evidence_source_url == "")
            )
        ).scalar_one()
        contacts_on_non_authoritative_source = session.execute(
            select(func.count(ScholarshipOfficialContact.id)).where(
                ScholarshipOfficialContact.evidence_source_type.not_in(
                    AUTHORITATIVE_SOURCE_TYPES
                )
            )
        ).scalar_one()
        orphan_contacts = session.execute(
            select(func.count(ScholarshipOfficialContact.id)).where(
                ScholarshipOfficialContact.scholarship_id.not_in(select(Scholarship.id))
            )
        ).scalar_one()
        contact_emails_verified = session.execute(
            select(func.count(ScholarshipOfficialContact.id)).where(
                ScholarshipOfficialContact.contact_email.isnot(None),
                ScholarshipOfficialContact.contact_email_verified.is_(True),
            )
        ).scalar_one()
        # An address stored but not confirmed must be zero at publish time, because
        # nothing downstream re-checks the flag on a contact it cannot see.
        contact_emails_stored_unverified = session.execute(
            select(func.count(ScholarshipOfficialContact.id)).where(
                ScholarshipOfficialContact.contact_email.isnot(None),
                ScholarshipOfficialContact.contact_email_verified.is_(False),
            )
        ).scalar_one()

    return {
        # Coverage
        "total_scholarship_rows": invariant["total_scholarships"],
        "coverage_rows": invariant["coverage_rows"],
        "coverage_invariant_holds": invariant["invariant_holds"],
        "missing_coverage_ids": invariant["missing_coverage_ids"][:50],
        "count_drift_ids": invariant["count_drift_ids"][:50],
        "coverage_by_status": invariant["by_status"],
        "scholarships_with_verified_supervisors": invariant[
            "scholarships_with_verified_supervisors"
        ],
        "scholarships_with_zero_verified_supervisors": invariant[
            "scholarships_without_verified_supervisors"
        ],
        # Canonical production universe
        "universe": universe["universe"],
        "universe_predicate_source": universe["universe_predicate_source"],
        "universe_size": universe["universe_size"],
        "universe_covered": universe["covered_in_universe"],
        "universe_uncovered_ids": universe["uncovered_in_universe"][:50],
        "universe_invariant_holds": universe["invariant_holds"],
        "coverage_rows_outside_universe": universe["coverage_rows_outside_universe"][:50],
        # Provenance
        "total_unique_professors": session.execute(
            select(func.count(ProfessorProfile.id))
        ).scalar_one(),
        "total_professor_links": total_links,
        "verified_professor_links": verified_links,
        "relationships_with_evidence": session.execute(
            select(func.count(ScholarshipProfessorLink.id)).where(
                ScholarshipProfessorLink.evidence_source_url.isnot(None),
                ScholarshipProfessorLink.evidence_source_url != "",
            )
        ).scalar_one(),
        "relationships_without_evidence": links_without_source,
        "verified_relationships_on_non_authoritative_source": links_on_secondary,
        "verified_official_emails": verified_emails,
        "unverified_emails_stored": unverified_emails_stored,
        "availability_by_state": availability_states,
        "availability_without_source": availability_without_source,
        "duplicate_professor_profiles": duplicate_profiles,
        "orphan_professor_links": orphan_links,
        "source_evidence_rows": session.execute(
            select(func.count(SupervisorSourceEvidence.id))
        ).scalar_one(),
        # Official contacts
        "contacts_table_present": contacts_present,
        "official_contacts": total_contacts,
        "contacts_without_evidence": contacts_without_evidence,
        "contacts_on_non_authoritative_source": contacts_on_non_authoritative_source,
        "orphan_contacts": orphan_contacts,
        "contact_emails_verified": contact_emails_verified,
        "contact_emails_stored_unverified": contact_emails_stored_unverified,
    }


def run_discovery(session: Session, limit: int, workers: int) -> None:
    from app.services.supervisor_discovery import run_discovery_batch

    for outcome in run_discovery_batch(session, limit=limit, max_workers=workers):
        logger.info(
            "discovery id=%s status=%s pages=%s professors=%s links=%s detail=%s",
            outcome.scholarship_id,
            outcome.status,
            outcome.pages_fetched,
            outcome.professors_found,
            outcome.links_written,
            outcome.detail or "",
        )


def evaluate(report: dict) -> list[str]:
    """Return every invariant that failed. An empty list means the run is clean."""
    failures = []
    if not report["coverage_invariant_holds"]:
        failures.append("coverage invariant does not hold")
    if not report["universe_invariant_holds"]:
        failures.append("canonical CATALOGUE universe is not fully covered")
    if report["relationships_without_evidence"]:
        failures.append(
            f"{report['relationships_without_evidence']} relationship(s) have no source"
        )
    if report["verified_relationships_on_non_authoritative_source"]:
        failures.append(
            f"{report['verified_relationships_on_non_authoritative_source']} verified "
            "relationship(s) rest on a non-authoritative source"
        )
    if report["availability_without_source"]:
        failures.append(
            f"{report['availability_without_source']} availability claim(s) have no source"
        )
    if report["duplicate_professor_profiles"]:
        failures.append(
            f"{report['duplicate_professor_profiles']} duplicate professor profile(s)"
        )
    if report["orphan_professor_links"]:
        failures.append(f"{report['orphan_professor_links']} link(s) reference a missing scholarship")
    # Contacts are held to the same two rules: a source behind every claim, and
    # no address stored without one.
    if report["contacts_without_evidence"]:
        failures.append(
            f"{report['contacts_without_evidence']} official contact(s) have no source"
        )
    if report["contacts_on_non_authoritative_source"]:
        failures.append(
            f"{report['contacts_on_non_authoritative_source']} official contact(s) rest "
            "on a non-authoritative source"
        )
    if report["orphan_contacts"]:
        failures.append(
            f"{report['orphan_contacts']} contact(s) reference a missing scholarship"
        )
    if report["contact_emails_stored_unverified"]:
        # Not a failure of the read path - the response gates on the flag - but
        # an address with no confirmation behind it is counted as a liability
        # rather than ignored, exactly as an unconfirmed professor address is.
        logger.warning(
            "%s contact email(s) are stored but unconfirmed; none is published",
            report["contact_emails_stored_unverified"],
        )
    return failures


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Backfill and report supervisor coverage")
    parser.add_argument("--report-only", action="store_true", help="Measure without writing")
    parser.add_argument("--coverage-only", action="store_true", help="Do not contact any university")
    parser.add_argument(
        "--discover", action="store_true", help="Also run discovery. Makes outbound requests."
    )
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--exclude-archived", action="store_true")
    parser.add_argument(
        "--rollback-coverage",
        action="store_true",
        help="Remove coverage rows only. Professor data is left intact.",
    )
    args = parser.parse_args()

    if not args.report_only:
        init_database()
    engine = get_engine()
    session = get_session_factory()()

    try:
        if args.rollback_coverage:
            rollback_coverage(session)
        elif not args.report_only:
            created = ensure_coverage(
                session, args.batch_size, include_archived=not args.exclude_archived
            )
            logger.info("coverage backfill complete: %s new row(s)", created)

        if args.discover:
            run_discovery(session, args.limit, args.workers)

        report = data_quality_report(session)
        print(json.dumps(report, indent=2, sort_keys=True))

        failures = evaluate(report)
        if failures:
            for failure in failures:
                logger.error("INVARIANT FAILED: %s", failure)
            sys.exit(1)
        logger.info("All supervisor invariants hold.")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()