"""The borrowed-role defect, pinned against the real page that exposed it.

A pre-production replay of Supervisor discovery against the NTU chancellery page
(``www.ntu.edu.sg/about-us/sustainability/about-us/meet-our-team``) produced six
candidates. Four name people:

    S Chandra Das (honorific "mr"), Jennie Chua ("ms"),
    Chua Thian Poh ("dr"), Yaacob bin Ibrahim ("prof")

Two do not:

    "Non-Academic Services"  role "academic"
    "Nanyang Research"       role "researcher"

Both reached the storage gate as ``inline_role`` and both were written
VERIFIED - a service listing and a research centre about to become verified
professors. Neither the role-removal test nor the surface form can catch them,
and the reason is worth stating precisely.

**Borrowed role, different shape.** "Academic Staff" states the role and *is*
the label, so removing the role leaves nothing. These two state a role somewhere
else and borrow it:

    "Nanyang Research | Researchers" - a heading, beside a role
    "Non-Academic Services"          - contains "academic" only inside a
                                       compound that negates it

**Surface form is identical.** "Nanyang Research" and "S Chandra Das" are both
two capitalised words. No word list separates them - that is the same dead end
this module has already ruled out once, for place and organisation names.

So the question cannot be re-derived at the storage gate. It is answered once,
in :func:`classify_person_candidate`, while the segments are still in hand: did
*this* segment claim a person, or did it inherit one from a neighbour? The answer
travels as ``PersonSignal.name_claims_person`` and on to
``FacultyCandidate.name_claims_person``. Only ``inline_role`` evidence is held to
it, because an honorific leads its own name and a profile role is read off that
person's own page - neither can borrow anything.

The invariant pinned here:

    A role claimed by a neighbouring segment claims that neighbour's people, not
    this name.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.supervisor_discovery import (  # noqa: E402
    FacultyCandidate,
    _verification_status_for,
)
from app.services.supervisor_person import (  # noqa: E402
    academic_role_in,
    classify_person_candidate,
)

NTU_DIRECTORY = (
    "https://www.ntu.edu.sg/about-us/sustainability/about-us/meet-our-team"
)

#: The two labels the real page yielded, with the href each was served from.
#: Both are first-party links on the institution's own host, so nothing about the
#: host or the URL was wrong; the label itself is what is not a person.
BORROWED_ROLE_LABELS = [
    ("Non-Academic Services", "academic",
     "https://www.ntu.edu.sg/education/accessible-education/non-academic-support"),
    ("Nanyang Research", "researcher",
     "https://www.ntu.edu.sg/education/talent-outreach/nrpjr"),
]

#: The four real people from that same page, as the storage gate sees them.
NTU_PEOPLE = [
    ("S Chandra Das", "mr", "honorific"),
    ("Jennie Chua", "ms", "honorific"),
    ("Chua Thian Poh", "dr", "honorific"),
    ("Yaacob bin Ibrahim", "prof", "honorific"),
]


def _candidate(name, url, role, evidence, **extra):
    return FacultyCandidate(
        name=name, profile_url=url, role=role, role_evidence=evidence, **extra
    )


def _verified(candidate) -> bool:
    return _verification_status_for(candidate).upper() == "VERIFIED"


# ---------------------------------------------------------------------------
# the classifier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label,role,url", BORROWED_ROLE_LABELS)
def test_a_role_nested_in_a_compound_is_not_a_role_the_text_states(label, role, url):
    """"Non-Academic" negates the role; it does not state it.

    Matching "academic" inside the hyphenated token and then removing it left
    the fragment "Non-" to satisfy the name test, so the listing looked like a
    person once the role had been taken out of it. A role phrase has to stand as
    its own word to be one.
    """
    assert academic_role_in(label) is None, (
        f"{label!r} does not state a role as its own word, so it states none"
    )


@pytest.mark.parametrize("label,role,url", BORROWED_ROLE_LABELS)
def test_a_sibling_segment_cannot_vouch_for_a_name_it_neighbours(label, role, url):
    """The claim has to come from the name's own segment, not a neighbour's.

    Either outcome is safe - refused outright, or accepted with the borrowed
    claim recorded as False - so both are asserted rather than skipped. A skip
    here would leave the case uncovered, which is the one thing this test exists
    to prevent.
    """
    signal = classify_person_candidate(
        f"{label} | Researchers",
        url=url,
        directory_context=True,
    )
    if signal is None:
        return  # rejected outright: nothing to vouch for, so nothing was vouched
    assert signal.name_claims_person is False, (
        f"{signal.name!r} borrowed the role from a neighbouring segment, so it "
        f"has claimed no person of its own"
    )


def test_the_compound_boundary_does_not_reject_a_leading_role():
    """The correction must not cost the case 91bcdb5 already fixed."""
    for label in ("Academic Staff", "Academic Planning"):
        assert academic_role_in(label) == "academic", (
            f"{label!r} does state a role, and must still be seen to state one"
        )


# ---------------------------------------------------------------------------
# the storage gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label,role,url", BORROWED_ROLE_LABELS)
def test_a_borrowed_role_cannot_reach_verified(label, role, url):
    assert not _verified(
        _candidate(label, url, role, "inline_role", name_claims_person=False)
    ), f"{label!r} borrowed its role and must not become a verified professor"


def test_the_four_real_people_are_still_verified():
    for name, role, evidence in NTU_PEOPLE:
        assert _verified(
            _candidate(
                name,
                f"https://www.ntu.edu.sg/about-us/the-chancellery/{name.lower()}",
                role,
                evidence,
            )
        ), f"{name!r} is a real person and must not be caught by this fix"


def test_a_name_that_states_its_own_role_is_still_verified():
    """The borrowed-role rule must not refuse the shape 91bcdb5 preserved."""
    assert _verified(
        _candidate(
            "Rachit Agarwal",
            "https://www.cs.cornell.edu/people/rachit-agarwal",
            "professor",
            "inline_role",
            name_claims_person=True,
        )
    )


def test_a_borrowed_role_row_is_never_created_at_all():
    """``_persist_candidates`` must skip it, not merely mark it unverified.

    Unverified-but-stored is a professor row a reviewer has to notice. Not
    stored is not a row.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.models import Base, Scholarship
    from app.models_supervisor import ProfessorProfile
    from app.services.supervisor_discovery import _persist_candidates

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    scholarship = Scholarship(
        title="NTU Nanyang President's Graduate Scholarship",
        country="Singapore",
        degree="Master",
        funding="Full",
        official_source="NTU",
        official_source_url=(
            "https://www.ntu.edu.sg/admissions/graduate/financialmatters/scholarships"
        ),
        verification_status="active",
        is_verified=True,
        status="open",
    )
    db.add(scholarship)
    db.commit()

    candidates = [
        _candidate(label, url, role, "inline_role", name_claims_person=False)
        for label, role, url in BORROWED_ROLE_LABELS
    ] + [
        _candidate(name, f"https://www.ntu.edu.sg/x/{name}", role, evidence)
        for name, role, evidence in NTU_PEOPLE
    ]

    stored = _persist_candidates(
        db,
        scholarship,
        candidates,
        faculty_url=NTU_DIRECTORY,
        institution_name="Nanyang Technological University",
        directory_html="<html></html>",
        http_status=200,
        discovery_path="static",
    )
    db.commit()

    names = sorted(row.canonical_name for row in db.execute(select(ProfessorProfile)).scalars())
    assert stored == len(NTU_PEOPLE), "only the four real people may be stored"
    assert names == sorted(name for name, _, _ in NTU_PEOPLE)
    assert "Non-Academic Services" not in names
    assert "Nanyang Research" not in names
    db.close()