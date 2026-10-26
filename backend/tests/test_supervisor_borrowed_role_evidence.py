"""The borrowed-role defect, pinned against the real page that exposed it.

A pre-production replay of Supervisor discovery against NTU's chancellery page
(``www.ntu.edu.sg/about-us/sustainability/about-us/meet-our-team``) produced six
candidates. Four name people:

    S Chandra Das ("mr"), Jennie Chua ("ms"),
    Chua Thian Poh ("dr"), Yaacob bin Ibrahim ("prof")

Two do not:

    "Non-Academic Services"   role "academic"
    "Nanyang Research"        role "researcher"

Both were admitted by ``supervisor_gating`` and stored. A one-shot production run
against scholarship 107 would therefore have written a service listing and a
research centre into ``professor_profiles`` as verified professors.

**Why the existing personhood gate missed them.** It asks two questions: is the
name the shape of one person's name, and is anything left once the role is
removed? "Academic Staff" fails the second, which is how 91bcdb5 caught it. These
two state a role somewhere else and borrow it:

    "Nanyang Research | Researchers"  a heading, and a role in the next segment
    "Non-Academic Services"           "academic" only inside a compound that
                                       negates it

Removing the role from the first changes nothing, because the role is not in that
segment at all. The residue is two capitalised words, which passes.

**Why surface form cannot be the answer.** "Nanyang Research" and "S Chandra Das"
are the same shape - two capitalised words. No word list separates them, and this
module has already ruled that shape out once, for place and organisation names.

So the question is answered where it can be: in ``classify_person_candidate``,
which still has the segments in hand, and travels as
``PersonSignal.name_claims_person``.

**The trade-off this makes, stated plainly.** The borrowed-role shape is the same
for a label and for a person::

    "Nanyang Research | Researchers"   refused   (a research centre)
    "Chua Thian Poh - Dr"               refused   (a real person)

Surface form cannot tell those apart, so the gate refuses both. That is a false
negative - a genuine person not stored - in exchange for not storing a false
positive, and the two failures are not symmetric: an absent person is reported
honestly as fewer verified supervisors found, while a research centre stored as a
professor is bad data that reads as good data. Neither real source produced the
false-negative shape: the four NTU people are read with the honorific leading the
name, and the Cornell fourteen carry a role read off their own profile page. Both
are outside this gate's reach and stay verified.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.supervisor_discovery import FacultyCandidate  # noqa: E402
from app.services.supervisor_gating import (  # noqa: E402
    SupervisorGate,
    approve_candidate_set,
)
from app.services.supervisor_person import (  # noqa: E402
    academic_role_in,
    classify_person_candidate,
)

HOST = "www.ntu.edu.sg"

BORROWED_ROLE_LABELS = [
    ("Non-Academic Services", "academic",
     "https://www.ntu.edu.sg/education/accessible-education/non-academic-support"),
    ("Nanyang Research", "researcher",
     "https://www.ntu.edu.sg/education/talent-outreach/nrpjr"),
]

NTU_PEOPLE = [
    ("S Chandra Das", "mr", "honorific",
     "https://www.ntu.edu.sg/about-us/the-chancellery/mr-s.-chandra-das"),
    ("Jennie Chua", "ms", "honorific",
     "https://www.ntu.edu.sg/about-us/the-chancellery/ms-jennie-chua"),
    ("Chua Thian Poh", "dr", "honorific",
     "https://www.ntu.edu.sg/about-us/the-chancellery/dr-chua-thian-poh"),
    ("Yaacob bin Ibrahim", "prof", "honorific",
     "https://www.ntu.edu.sg/about-us/the-chancellery/prof-yaacob-bin-ibrahim"),
]


def _approve(candidate, faculty_url=None):
    result = approve_candidate_set(
        [candidate],
        seed_host=HOST,
        faculty_url=faculty_url or candidate.profile_url,
    )
    return result


# ---------------------------------------------------------------------------
# the role matcher
# ---------------------------------------------------------------------------


def test_a_role_nested_in_a_compound_is_not_a_role_the_text_states():
    """"Non-Academic" negates the role rather than stating it.

    Matching "academic" inside the hyphenated token, then removing it, left the
    fragment "Non-" to satisfy the two-token name test - so the listing looked
    like a person once the role had been taken out of it. A role phrase has to
    stand as its own word to be one.
    """
    assert academic_role_in("Non-Academic Services") is None
    # And the case 91bcdb5 fixed must be untouched.
    assert academic_role_in("Academic Staff") == "academic"
    assert academic_role_in("Academic Planning") == "academic"


# ---------------------------------------------------------------------------
# the classifier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("anchor", [
    "Non-Academic Services",
    "Nanyang Research",
    "Nanyang Research | Researchers",
])
def test_the_real_page_labels_never_become_a_person_claim(anchor):
    """Whatever the classifier does, it must not vouch for these labels.

    Rejecting the anchor outright is the best outcome and is accepted. Being
    accepted while claiming no person is also correct, because that is what the
    gate reads. The one unacceptable outcome is a signal that claims a person.
    """
    url = BORROWED_ROLE_LABELS[1][2]
    signal = classify_person_candidate(anchor, url=url, directory_context=True)
    if signal is None:
        return  # rejected outright: nothing claimed, nothing to vouch for
    assert signal.name_claims_person is False, (
        f"{signal.name!r} borrowed the role {signal.role!r} from a neighbouring "
        f"segment and must not claim a person"
    )


@pytest.mark.parametrize("anchor,expected_role", [
    ("Dr Chua Thian Poh", "dr"),
    ("Rachit Agarwal Professor", "professor"),
])
def test_a_name_that_makes_its_own_claim_still_does(anchor, expected_role):
    signal = classify_person_candidate(
        anchor, url="https://x.edu/people/y", directory_context=True
    )
    assert signal is not None
    assert signal.name_claims_person is True
    assert signal.role == expected_role


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,role,url", BORROWED_ROLE_LABELS)
def test_a_borrowed_role_is_refused_by_the_personhood_gate(name, role, url):
    candidate = FacultyCandidate(
        name=name, profile_url=url, role=role,
        role_evidence="inline_role", name_claims_person=False,
    )
    result = _approve(candidate)
    assert not result.approved, f"{name!r} must not be approved for storage"
    assert result.reasons_for(SupervisorGate.PERSONHOOD) >= 1, (
        "the refusal must be attributed to personhood, so the reason is legible "
        f"in the audit trail; reasons were {result.rejection_reasons}"
    )


@pytest.mark.parametrize("name,role,evidence,url", NTU_PEOPLE)
def test_the_four_real_people_are_still_approved(name, role, evidence, url):
    candidate = FacultyCandidate(
        name=name, profile_url=url, role=role,
        role_evidence=evidence, name_claims_person=True,
    )
    result = _approve(candidate)
    assert [c.name for c in result.approved] == [name], (
        f"{name!r} is a real person and must not be caught by this fix"
    )


def test_a_candidate_that_never_recorded_a_claim_is_refused():
    """Absent means "no claim recorded", which is the conservative reading.

    ``FacultyCandidate`` defaults the flag to True so hand-built candidates keep
    working, so this pins the gate's own behaviour for an object that genuinely
    does not carry the attribute - the case where "unknown" must not be read as
    "yes".
    """

    class NoFlag:
        name = "Some Person"
        profile_url = "https://www.ntu.edu.sg/x"
        title = None
        role = "professor"
        role_evidence = "inline_role"

    result = _approve(NoFlag(), "https://www.ntu.edu.sg/directory")
    assert not result.approved, (
        "a candidate with no recorded claim must not be stored"
    )


def test_the_whole_real_page_yields_only_its_people():
    """The page's own six candidates, through the real classifier and the gate."""
    extracted = {}
    for name, role, url in BORROWED_ROLE_LABELS:
        for anchor in (name, f"{name} | Researchers", f"{name} - Support"):
            signal = classify_person_candidate(
                anchor, url=url, directory_context=True
            )
            if signal is not None:
                extracted[anchor] = signal

    for anchor, signal in extracted.items():
        candidate = FacultyCandidate(
            name=signal.name, profile_url=url_of(anchor),
            role=signal.role, role_evidence=signal.role_evidence,
            name_claims_person=signal.name_claims_person,
        )
        result = _approve(candidate)
        assert not result.approved, (
            f"{anchor!r} classified to {signal.name!r} but was approved for storage"
        )

    for name, role, evidence, url in NTU_PEOPLE:
        candidate = FacultyCandidate(
            name=name, profile_url=url, role=role,
            role_evidence=evidence, name_claims_person=True,
        )
        assert [c.name for c in _approve(candidate).approved] == [name]


def url_of(anchor: str) -> str:
    for name, _role, url in BORROWED_ROLE_LABELS:
        if anchor.startswith(name):
            return url
    raise AssertionError(f"unknown anchor {anchor!r}")


# ---------------------------------------------------------------------------
# the sibling case, pinned deliberately
# ---------------------------------------------------------------------------


def test_a_name_whose_role_sits_in_a_neighbour_is_not_vouched_for():
    """The cost of this fix, stated as a test rather than left implicit.

    "Chua Thian Poh - Dr" is a real person whose role is in the second segment,
    and it is the same structural shape as "Nanyang Research | Researchers". No
    surface-form rule separates them, so this refuses both. The false negative is
    preferred to the false positive: a person not stored is reported honestly as
    fewer verified supervisors, while a research centre stored as a professor is
    bad data that reads as good data.

    Neither real source produces this shape - the NTU people are read with the
    honorific leading the name, and the Cornell fourteen carry a role read off
    their own profile page - so nothing measured is lost to it.
    """
    signal = classify_person_candidate(
        "Chua Thian Poh - Dr", url="https://www.ntu.edu.sg/x", directory_context=True
    )
    assert signal is not None, "the segment pair should still classify somehow"
    assert signal.role == "dr"
    assert signal.name_claims_person is False, (
        "the role belongs to the second segment, so the first has claimed nobody"
    )


def test_extraction_carries_the_classifiers_verdict():
    """The verdict must survive the trip from the classifier to the candidate.

    Structural rather than behavioural, because the only pages that currently
    produce a borrowed-role claim are not reachable from a test without a network
    fetch. What must not regress is the wiring: the field exists on the
    classifier's signal, and the extraction site passes it on. Losing either line
    leaves a flag that is always True and therefore never consulted.
    """
    import inspect
    import io
    import tokenize
    from pathlib import Path

    import app.services.supervisor_discovery as discovery_module
    from app.services.supervisor_person import PersonSignal

    assert "name_claims_person" in PersonSignal.__dataclass_fields__, (
        "the classifier must record the verdict"
    )

    source_path = Path(inspect.getfile(discovery_module)).resolve()
    kept: list[str] = []
    with source_path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in (tokenize.STRING, tokenize.COMMENT):
                continue
            kept.append(token.string)
    code = " ".join(kept)

    assert "name_claims_person" in code, (
        "FacultyCandidate must carry the verdict"
    )
    assert "name_claims_person=signal.name_claims_person" in code.replace(" ", ""), (
        "extraction must pass the classifier's verdict through; without this the "
        "field keeps its default and no borrowed-role claim is ever caught"
    )