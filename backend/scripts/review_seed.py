"""Seed a temporary database so the browser review can see every supervisor state.

Synthetic records, in a scratch file, for the duration of a review. Nothing here
touches ScholarZone's real catalogue, its schema in any deployed environment, or
any production data - the point is to give the frontend real API responses in
each state so the rendering can be inspected rather than assumed.

Four scholarships, one per state the panel must distinguish:

  1. a verified professor with a published email and availability
  2. no verified supervisor found
  3. discovery pending
  4. the source requires rendering (the inconclusive state)

The fifth asserts something more valuable: that nothing in the UI claims a
professor was verified when no professor exists.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.models import Base, Scholarship  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorAvailability,
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
)
from app.services.supervisor_status import (  # noqa: E402
    AvailabilityScope,
    AvailabilityState,
    ProfessorRelationshipType,
    RelationshipVerificationStatus,
    SourceType,
    SupervisorCoverageStatus,
)

TARGET = os.environ["REVIEW_DB_PATH"]


# Every fixture shares one invented country so the review can filter the
# catalogue down to exactly these four cards with ?country=Aurelia. The
# application seeds its own catalogue into whatever database it is pointed
# at, so filtering is what makes the card affordance observable at all.
def make(index: int, title: str, country: str, **overrides) -> Scholarship:
    base = {
        "title": title,
        "country": country,
        "degree": "Master",
        "funding": "Fully Funded",
        "description": "A synthetic record used only to review the supervisor UI.",
        "status": "open",
        "deadline_date": date(2027, 1, 15),
        "deadline_precision": "exact",
        "eligibility": ["Open to international applicants."],
        "coverage": ["Full tuition", "Stipend"],
        "benefits": [],
        "requirements": [],
        "documents": [],
        "official_source": "Test University",
        "official_source_url": f"https://uni{index}.edu/programmes/{index}",
        "official_updates_url": None,
        "catalogue_url": None,
        "is_verified": True,
        "verification_status": "active",
        "image_url": None,
        "image_kind": None,
    }
    base.update(overrides)
    return Scholarship(**base)


def main() -> None:
    if os.path.exists(TARGET):
        os.remove(TARGET)

    engine = create_engine(f"sqlite:///{TARGET}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    verified = make(
        1,
        "MSc Computer Science (review fixture)",
        "Aurelia",
        image_url="https://picsum.photos/seed/sz1/800/500",
    )
    empty = make(
        2,
        "MA Linguistics (review fixture)",
        "Aurelia",
        image_url="https://picsum.photos/seed/sz2/800/500",
    )
    pending = make(
        3,
        "MSc Data Science (review fixture)",
        "Aurelia",
        image_url="https://picsum.photos/seed/sz3/800/500",
    )
    render = make(
        4,
        "BSc Environmental Science (review fixture)",
        "Aurelia",
        image_url="https://picsum.photos/seed/sz4/800/500",
    )
    for row in (verified, empty, pending, render):
        session.add(row)
    session.commit()
    for row in (verified, empty, pending, render):
        session.refresh(row)

    now = datetime.now(timezone.utc)

    professor = ProfessorProfile(
        canonical_name="Dr Ada Lovelace",
        title="Professor",
        institution_name="Test University",
        department_name="School of Computing",
        official_profile_url="https://uni1.edu/people/ada-lovelace",
        official_email="a.lovelace@uni1.edu",
        official_email_verified=True,
        research_areas=["Machine Learning", "Formal Verification"],
        last_verified_at=now,
    )
    session.add(professor)
    session.commit()
    session.refresh(professor)

    session.add(
        ScholarshipProfessorLink(
            scholarship_id=verified.id,
            professor_id=professor.id,
            relationship_type=str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
            evidence_source_url="https://uni1.edu/people/faculty",
            evidence_source_type=str(SourceType.OFFICIAL_DEPARTMENT_PAGE),
            evidence_quote_or_summary="Listed on the Faculty of Computing page.",
            retrieved_at=now,
            verified_at=now,
            verification_status=str(RelationshipVerificationStatus.VERIFIED),
            confidence=90,
        )
    )
    session.add(
        ProfessorAvailability(
            professor_id=professor.id,
            scope=str(AvailabilityScope.MASTERS_SUPERVISION),
            state=str(AvailabilityState.NOT_PUBLISHED),
            source_url="https://uni1.edu/people/ada-lovelace",
            verified_at=now,
        )
    )
    session.add(
        ProfessorAvailability(
            professor_id=professor.id,
            scope=str(AvailabilityScope.FUNDING),
            state=str(AvailabilityState.NOT_PUBLISHED),
            source_url="https://uni1.edu/people/ada-lovelace",
            verified_at=now,
        )
    )

    states = [
        (verified, SupervisorCoverageStatus.VERIFIED_SUPERVISORS, 1, "complete"),
        (empty, SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND, 0, "complete"),
        (pending, SupervisorCoverageStatus.SEARCH_PENDING, 0, "not_collected"),
        (
            render,
            SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING,
            0,
            "partial",
        ),
    ]
    for row, status, count, evidence in states:
        session.add(
            ScholarshipSupervisorCoverage(
                scholarship_id=row.id,
                status=str(status),
                verified_supervisor_count=count,
                evidence_state=evidence,
                last_checked_at=now if count or status != SupervisorCoverageStatus.SEARCH_PENDING else None,
                next_check_at=now + timedelta(days=7),
                last_error_summary=(
                    "The faculty page is assembled by JavaScript. A bounded browser render produced "
                    "no academic evidence, so no supervisor can be verified either way."
                    if status == SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING
                    else None
                ),
            )
        )
    session.commit()

    # Captured before teardown: reading a mapped attribute after the session is
    # closed detaches the instance and raises.
    summary = [
        (row.id, row.title, str(state))
        for row, state, _count, _evidence in states
    ]
    session.close()
    engine.dispose()

    print("review fixture database written")
    for identifier, title, state in summary:
        print(f"  id={identifier} {title} -> {state}")


if __name__ == "__main__":
    main()