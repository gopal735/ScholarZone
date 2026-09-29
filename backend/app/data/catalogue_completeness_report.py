"""Catalogue-wide completeness report.

The point of this report is that "the record is missing a logo" and "we could
not reach the site to look for one" are different facts with different
consequences, and a single number cannot express both. Collapsing them is how a
collection failure came to be reported as a permanent absence.

Every value is a real database count. Nothing here estimates, extrapolates or
rounds into a percentage that was not measured.
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Scholarship


def _count(session: Session, *conditions) -> int:
    return int(
        session.scalar(select(func.count(Scholarship.id)).where(*conditions)) or 0
    )


def build_report(factory: sessionmaker[Session]) -> dict:
    """Deterministic catalogue-wide counts, grouped by why they failed."""
    session = factory()
    try:
        quarantined = Scholarship.verification_status == "quarantined"
        valid = Scholarship.verification_status != "quarantined"
        verified = valid & Scholarship.is_verified.is_(True)

        by_status = dict(
            session.execute(
                select(Scholarship.image_evaluation_status, func.count())
                .where(valid)
                .group_by(Scholarship.image_evaluation_status)
            ).all()
        )

        total = _count(session)
        q_total = _count(session, quarantined)
        v_total = total - q_total
        verified_count = _count(session, verified)

        has_image = valid & Scholarship.image_url.isnot(None)
        has_verified_image = valid & Scholarship.image_verified_at.isnot(None)
        official_image = has_verified_image & (Scholarship.image_source_type != "wikimedia")

        return {
            # -- totals -----------------------------------------------------
            "total_records": total,
            "total_valid": v_total,
            "fully_verified_scholarships": verified_count,
            "quarantined": q_total,
            "review_pending": _count(
                session,
                Scholarship.verification_status == "needs_review",
            ),
            # -- data completeness (DATA MISSING) --------------------------
            "records_missing_provider": _count(session, verified, _blank(Scholarship.official_source)),
            "records_missing_degree": _count(session, verified, _blank(Scholarship.degree)),
            "records_missing_funding": _count(session, verified, _blank(Scholarship.funding)),
            "records_missing_description": _count(session, verified, Scholarship.description.is_(None)),
            "records_missing_deadline": _count(session, verified, Scholarship.deadline_date.is_(None)),
            "records_missing_eligibility": _count(session, verified, _empty_list(Scholarship.eligibility)),
            "records_missing_application_url": _count(
                session, verified, _blank(Scholarship.application_link)
            ),
            # -- image outcomes, kept separate by cause ---------------------
            # A blocked source is NOT an absence of a logo. It is a
            # collection failure that may succeed on a later run.
            "source_blocked": int(by_status.get("source_blocked", 0)),
            "source_unreachable": int(by_status.get("source_unreachable", 0)),
            "no_official_logo": int(by_status.get("no_official_image", 0)),
            "invalid_candidates": int(by_status.get("invalid_candidates", 0)),
            "image_pending": int(by_status.get("pending", 0)),
            "image_error": int(by_status.get("error", 0)),
            "third_party_only": _count(
                session, valid, Scholarship.image_source_type == "wikimedia"
            ),
            "records_with_official_image": _count(session, official_image),
            "records_missing_official_image": v_total - _count(session, official_image),
            "records_with_any_image": _count(session, has_image),
            "records_with_unvalidated_image": _count(session, has_image, Scholarship.image_verified_at.is_(None)),
            # -- the honest summary ----------------------------------------
            "unresolved_image_total": v_total - _count(session, official_image),
        }
    finally:
        session.close()


def _blank(column):
    """Blank or a placeholder the scraper invented.

    ``"Unknown"`` is counted as missing on purpose: it is not a value the
    provider stated, it is an absence wearing a value's clothes.
    """
    return (column.is_(None)) | (column == "") | (column.ilike("unknown")) | (column.ilike("n/a"))


def _empty_list(column):
    # A JSON/ARRAY column that is null or an empty array carries no information.
    from sqlalchemy import or_

    return or_(column.is_(None), column == [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from ..database import get_session_factory, init_database

    init_database()
    report = build_report(get_session_factory())

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    width = max(len(k) for k in report)
    print("=" * (width + 34))
    print("CATALOGUE COMPLETENESS")
    print("=" * (width + 34))
    for key, value in report.items():
        print(f"  {key:<{width}} : {value}")
    print("=" * (width + 34))
    print(
        "Note: source_blocked and source_unreachable are collection failures.\n"
        "      They are not evidence that a record has no logo."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
