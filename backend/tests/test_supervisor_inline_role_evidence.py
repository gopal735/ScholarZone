"""The inline-role defect, pinned against the real page that exposed it.

The Cornell Computer Science people directory returns sixteen labels that a role
vocabulary reads as academic. Fourteen name people. Two are navigation links:
"Academic Planning" and "Academic Staff".

Both reached the classifier's inline-role branch and were accepted, because the
branch took the first two tokens of the role-bearing segment as the name. For
"Academic Staff" that is the whole label, and the tokens include the role word
itself. The label then became a person called "Academic Staff" holding the role
"academic", and the storage gate - which asks only whether a role was stated -
promoted it to VERIFIED.

The invariant these tests pin is narrow and structural:

    A role word alone claims a category. Only a name surviving the removal of the
    role claims an individual.

So removing the role has to leave a person behind. "Rachit Agarwal Professor"
loses "Professor" and is still a name. "Academic Staff" loses "Academic" and
leaves one token that is not a name. Nothing here is a list of forbidden words,
so the same reasoning applies to a university nobody has written a test for.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from urllib.parse import urlparse

from app.services.supervisor_discovery import (  # noqa: E402
    FacultyCandidate,
    _verification_status_for,
)
from app.services.supervisor_gating import (  # noqa: E402
    SupervisorGate,
    approve_candidate_set,
)
from app.services.supervisor_person import (  # noqa: E402
    academic_role_in,
    classify_person_candidate,
    role_words_are_the_whole_name,
    states_role_about_a_person,
)

CORNELL_DIRECTORY = "https://www.cs.cornell.edu/people/"

#: The two navigation links the real directory yielded, with the URL each was
#: actually served from. The URLs matter: they show the failure was not caused by
#: an off-directory link, and the fragment case shows a `#` anchor is enough.
NAVIGATION_LABELS = [
    ("Academic Planning", "https://www.cs.cornell.edu/current-students#grad"),
    ("Academic Staff", "https://www.cs.cornell.edu/directory/academic-staff"),
]

#: Real people from that same page, in the shape the classifier returns them.
#: Each is at a personal-profile path, so they are accepted on directory
#: structure before enrichment, then carry profile_role afterwards.
CORNELL_PEOPLE = [
    "Rachit Agarwal",
    "Lorenzo Alvisi",
    "Andrew Appel",
    "William Arms",
    "Yoav Artzi",
    "Hadar Averbuch-Elor",
    "Shiri Azenkot",
    "Kavita Bala",
    "Tapomayukh Bhattacharjee",
    "David Bindel",
    "Ken Birman",
    "Florentina Bunea",
    "Diana Cai",
    "Claire Cardie",
]


# ---------------------------------------------------------------------------
# Test 1 - the Cornell fixture: 16 extracted, 14 people, 2 navigation links
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label,url", NAVIGATION_LABELS)
def test_cornell_navigation_links_are_not_people(label, url):
    """The exact two false positives, at the exact two URLs.

    Asserting the label alone is not enough: each is refused inside the directory
    that produced it, with directory context asserted, at its real URL.
    """
    assert classify_person_candidate(label, url=url, directory_context=True) is None, (
        f"{label!r} is a navigation label and must not classify as a person"
    )


@pytest.mark.parametrize("label,url", NAVIGATION_LABELS)
def test_cornell_navigation_links_cannot_be_verified(label, url):
    """The end-to-end claim: neither can reach VERIFIED by any route.

    Built by hand rather than extracted, so this fails if a future caller ever
    constructs such a candidate directly and bypasses the classifier.
    """
    candidate = FacultyCandidate(
        name=label,
        profile_url=url,
        role=academic_role_in(label),
        role_evidence="inline_role",
    )
    assert candidate.has_role_evidence, "precondition: a role word is present"
    assert role_words_are_the_whole_name(candidate.name, candidate.role)
    assert _verification_status_for(candidate) != "verified"


@pytest.mark.parametrize("name", CORNELL_PEOPLE)
def test_cornell_people_keep_their_correct_classification(name):
    """The fourteen must be untouched.

    The fix removes two candidates from a sixteen-candidate page. If it had also
    cost a real person that would be a worse failure than the defect, so each of
    the fourteen is asserted individually.
    """
    url = f"{CORNELL_DIRECTORY}{name.lower().replace(' ', '-')}"
    signal = classify_person_candidate(name, url=url, directory_context=True)
    assert signal is not None, f"{name!r} is a real academic and must be accepted"
    assert signal.name == name
    # On the listing page a bare name is accepted on structure, with no role yet.
    assert signal.role_evidence == "source_context"
    assert signal.academic_role_stated is False

    # After enrichment the profile page supplies the role, which is what makes
    # these VERIFIED rather than merely discoverable.
    enriched = FacultyCandidate(
        name=name,
        profile_url=url,
        role="professor",
        role_evidence="profile_role",
    )
    assert not role_words_are_the_whole_name(enriched.name, enriched.role)
    assert _verification_status_for(enriched) == "verified"


def test_the_fix_removes_exactly_two_of_sixteen():
    """The arithmetic of the real page, so a wider change cannot pass quietly."""
    sixteen = CORNELL_PEOPLE + [label for label, _ in NAVIGATION_LABELS]
    assert len(sixteen) == 16
    assert len(CORNELL_PEOPLE) == 14
    accepted = [
        label
        for label in sixteen
        if classify_person_candidate(
            label,
            url=f"{CORNELL_DIRECTORY}{label.lower().replace(' ', '-')}",
            directory_context=True,
        )
        is not None
    ]
    assert len(accepted) == 14
    assert not {"Academic Planning", "Academic Staff"} & set(accepted)


# ---------------------------------------------------------------------------
# Test 2 - the minimal inline-role fragment
# ---------------------------------------------------------------------------


def test_the_sixty_character_fragment_cannot_verify():
    """The reproduction from the defect report, as a permanent test.

    ``academic_role_in`` is unchanged and still reports a role: identifying
    role-like text is a legitimate question and the answer is still yes. What must
    not happen is that the answer convert into a person.
    """
    fragment = '<ul><li><a href="/directory/academic-staff">Academic Staff</a></li></ul>'

    # The role vocabulary still recognises the text.
    assert academic_role_in("Academic Staff") == "academic"

    candidates = __import__(
        "app.services.supervisor_discovery", fromlist=["extract_faculty_candidates"]
    ).extract_faculty_candidates(fragment, "https://www.cs.cornell.edu/people/", "cs.cornell.edu")
    for candidate in candidates:
        assert candidate.name != "Academic Staff"
        assert _verification_status_for(candidate) != "verified"


def test_role_text_alone_never_establishes_an_identity():
    """The invariant stated as a property of the vocabulary, not of two strings.

    Every role phrase is paired with a collective noun rather than a name. If any
    of these ever verified, the rule would be a string blacklist after all.
    """
    collectives = [
        "Academic Staff",
        "Professor Emeritus",
        "Researcher List",
        "Lecturer Directory",
        "Reader Panel",
        "Fellow Council",
        "Dean Committee",
    ]
    for label in collectives:
        role = academic_role_in(label)
        if role is None:
            continue
        assert not states_role_about_a_person(label, role), label
        assert role_words_are_the_whole_name(label, role), label


# ---------------------------------------------------------------------------
# Test 3 - genuine inline-role candidates survive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,expected_name,expected_role",
    [
        # The role sits in its own clause: the name is a sibling segment and was
        # never at risk. This exact case is in test_supervisor_person_policy.
        ("Jane Smith - Professor of Computer Science", "Jane Smith", "professor"),
        # The role trails the name in one clause. This is the case the fix had to
        # keep, and the closest legitimate neighbour of "Academic Staff".
        ("Rachit Agarwal Professor", "Rachit Agarwal", "professor"),
        ("Grace Hopper Reader", "Grace Hopper", "reader"),
        ("Ada Lovelace Lecturer", "Ada Lovelace", "lecturer"),
        # The role is read from the same clause as the name, so the removal has to
        # leave that name intact. "assistant professor" is reported as "professor"
        # because _find_role tests the shorter phrase first - unchanged behaviour,
        # recorded here so a future reordering is noticed.
        ("Kavita Bala Assistant Professor", "Kavita Bala", "professor"),
    ],
)
def test_genuine_inline_role_candidates_are_preserved(label, expected_name, expected_role):
    signal = classify_person_candidate(label)
    assert signal is not None, f"{label!r} names a person and must be accepted"
    assert signal.name == expected_name
    assert signal.role == expected_role
    assert signal.role_evidence == "inline_role"
    assert signal.academic_role_stated is True
    assert not role_words_are_the_whole_name(signal.name, signal.role)
    assert _verification_status_for(
        FacultyCandidate(
            name=signal.name,
            profile_url="https://uni1.edu/people/x",
            role=signal.role,
            role_evidence=signal.role_evidence,
        )
    ) == "verified"


# ---------------------------------------------------------------------------
# Test 4 - every other legitimate evidence type is unaffected
# ---------------------------------------------------------------------------


def test_honorific_evidence_is_unchanged():
    for label, name, role in [
        ("Dr Ada Lovelace", "Ada Lovelace", "dr"),
        ("Professor Alan Turing", "Alan Turing", "professor"),
    ]:
        signal = classify_person_candidate(label)
        assert signal is not None
        assert (signal.name, signal.role, signal.role_evidence) == (name, role, "honorific")


def test_source_context_evidence_is_unchanged():
    signal = classify_person_candidate(
        "Grace Hopper", url="https://uni1.edu/people/grace-hopper", directory_context=True
    )
    assert signal is not None
    assert signal.role_evidence == "source_context"
    assert signal.academic_role_stated is False


def test_profile_role_evidence_is_unchanged():
    """The evidence type the real Cornell people end up with after enrichment."""
    candidate = FacultyCandidate(
        name="Diana Cai",
        profile_url=f"{CORNELL_DIRECTORY}diana-cai",
        role="assistant professor",
        role_evidence="profile_role",
    )
    assert candidate.has_role_evidence
    assert not role_words_are_the_whole_name(candidate.name, candidate.role)
    assert _verification_status_for(candidate) == "verified"


def test_a_particle_surname_with_a_trailing_role_is_still_refused():
    """A pre-existing limitation this patch deliberately does not change.

    The role-bearing-clause fallback takes the first two tokens as the name, so
    "Grace van Dijk Professor" yields "Grace van", which is not person-shaped, and
    the label is refused. Confirmed identical on adb4dee: the patch removes the
    two navigation labels and costs nothing, but it does not widen that fallback
    either. Fixing it would be a separate change to name extraction.
    """
    assert classify_person_candidate("Grace van Dijk Professor") is None


def test_the_cheap_screen_is_still_only_narrower_than_the_classifier():
    """Unchanged contract: the screen may name a role, the classifier decides."""
    from app.services.supervisor_person import looks_like_a_person_name

    assert looks_like_a_person_name("Dr Ada Lovelace") is True
    assert looks_like_a_person_name("Grace Hopper") is False
    assert looks_like_a_person_name("Academic Staff") is True  # role text, still narrow


# ---------------------------------------------------------------------------
# Test 5 - the storage gate
# ---------------------------------------------------------------------------


def test_storage_gate_refuses_a_role_restated_as_a_name():
    """``_persist_candidates`` must skip it, not merely mark it unverified."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.models import Base, Scholarship
    from app.models_supervisor import ProfessorProfile, ScholarshipProfessorLink
    from sqlalchemy import select

    from app.services.supervisor_discovery import _persist_candidates

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    scholarship = Scholarship(
        title="Harness",
        country="United States",
        degree="Master's",
        funding="Varies",
        description="test harness",
        is_verified=True,
        official_source_url=CORNELL_DIRECTORY,
    )
    db.add(scholarship)
    db.flush()
    db.commit()

    fake = FacultyCandidate(
        name="Academic Staff",
        profile_url="https://www.cs.cornell.edu/directory/academic-staff",
        role="academic",
        role_evidence="inline_role",
    )
    genuine = FacultyCandidate(
        name="Rachit Agarwal",
        profile_url=f"{CORNELL_DIRECTORY}rachit-agarwal",
        role="professor",
        role_evidence="profile_role",
    )

    stored = _persist_candidates(
        db,
        scholarship,
        [fake, genuine],
        faculty_url=CORNELL_DIRECTORY,
        institution_name="Cornell University",
        directory_html="<html></html>",
        http_status=200,
        discovery_path="static_fetch",
    )
    db.commit()

    assert stored == 1, "only the genuine professor may be stored"
    names = [row.canonical_name for row in db.execute(select(ProfessorProfile)).scalars()]
    assert "Academic Staff" not in names
    assert names == ["Rachit Agarwal"]
    assert db.execute(select(ScholarshipProfessorLink)).scalars().all()


# ---------------------------------------------------------------------------
# Test 6 - the URL contract for inline-role evidence
# ---------------------------------------------------------------------------


def test_inline_role_requires_a_person_profile_url():
    """Inline-role evidence is person-eligible only when the profile URL is a
    personal-profile path. A programme page or research-centre link does not
    qualify, even if the remaining text looks like a name."""
    from app.services.supervisor_gating import approve_candidate_set

    candidate = FacultyCandidate(
        name="Nanyang Research",
        profile_url="https://www.ntu.edu.sg/education/talent-outreach/nrpjr",
        role="researcher",
        role_evidence="inline_role",
        name_claims_person=True,
    )
    result = approve_candidate_set([candidate], seed_host="www.ntu.edu.sg", faculty_url=candidate.profile_url)
    assert not result.approved
    assert result.reasons_for(SupervisorGate.PERSONHOOD) >= 1


def test_inline_role_with_person_profile_url_is_accepted():
    """A genuine inline-role person at a personal-profile path is unaffected."""
    from app.services.supervisor_gating import approve_candidate_set

    candidate = FacultyCandidate(
        name="Rachit Agarwal",
        profile_url="https://uni1.edu/people/rachit-agarwal",
        role="professor",
        role_evidence="inline_role",
        name_claims_person=True,
    )
    result = approve_candidate_set([candidate], seed_host="uni1.edu", faculty_url="https://uni1.edu/people/faculty")
    assert [c.name for c in result.approved] == ["Rachit Agarwal"]


@pytest.mark.parametrize(
    "label,url",
    [
        ("Nanyang Research Programme Junior Researcher (NRPjr)",
         "https://www.ntu.edu.sg/education/talent-outreach/nrpjr"),
        ("Nanyang Research",
         "https://www.ntu.edu.sg/education/talent-outreach/nrpjr"),
        ("Research Centre",
         "https://uni1.edu/research/centre"),
        ("Department of Computing",
         "https://uni1.edu/department/computing"),
        ("Student Services",
         "https://uni1.edu/services/students"),
        ("Admissions Office",
         "https://uni1.edu/admissions"),
    ],
)
def test_organisational_labels_with_inline_role_are_refused(label, url):
    """Programme, department, service, centre and programme names are refused
    when they carry inline-role evidence but no person-profile URL."""
    from app.services.supervisor_gating import approve_candidate_set

    role = academic_role_in(label)
    if role is None:
        role = "researcher"
    candidate = FacultyCandidate(
        name=label,
        profile_url=url,
        role=role,
        role_evidence="inline_role",
        name_claims_person=True,
    )
    result = approve_candidate_set([candidate], seed_host=urlparse(url).netloc, faculty_url=url)
    assert not result.approved, f"{label!r} at {url!r} must not be approved"


@pytest.mark.parametrize(
    "name,role,url",
    [
        ("S Chandra Das", "mr", "https://www.ntu.edu.sg/about-us/the-chancellery/mr-s.-chandra-das"),
        ("Jennie Chua", "ms", "https://www.ntu.edu.sg/about-us/the-chancellery/ms-jennie-chua"),
        ("Chua Thian Poh", "dr", "https://www.ntu.edu.sg/about-us/the-chancellery/dr-chua-thian-poh"),
        ("Yaacob bin Ibrahim", "prof", "https://www.ntu.edu.sg/about-us/the-chancellery/prof-yaacob-bin-ibrahim"),
    ],
)
def test_the_four_ntu_people_are_still_accepted(name, role, url):
    """The four legitimate NTU people remain approved. They use honorific
    evidence, so the inline-role URL contract does not apply to them."""
    from app.services.supervisor_gating import approve_candidate_set

    candidate = FacultyCandidate(
        name=name,
        profile_url=url,
        role=role,
        role_evidence="honorific",
        name_claims_person=True,
    )
    result = approve_candidate_set([candidate], seed_host="www.ntu.edu.sg", faculty_url=url)
    assert [c.name for c in result.approved] == [name]


def test_inline_role_candidate_with_navigational_slug_is_refused():
    """A URL under a person path root but with a navigational slug is still not
    a person profile, so inline-role evidence cannot rely on it."""
    from app.services.supervisor_gating import approve_candidate_set

    candidate = FacultyCandidate(
        name="Research Staff",
        profile_url="https://uni1.edu/people/faculty",
        role="researcher",
        role_evidence="inline_role",
        name_claims_person=True,
    )
    result = approve_candidate_set([candidate], seed_host="uni1.edu", faculty_url="https://uni1.edu/people/faculty")
    assert not result.approved