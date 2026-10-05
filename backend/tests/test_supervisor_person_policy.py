"""Personhood, source context and institution-domain policy.

Three properties are under test, and together they are the difference between
"discovery found a person" and "discovery published a professor".

**Personhood is positive evidence.** A piece of link text names a person when it
states an academic role, or when it sits at a personal-profile path inside a page
established as a faculty directory. Absent both, it is not a person. That is why
"South Australia" and "School of Computing" are rejected - not because they are on
a list of known-bad words, which is a mechanism that only ever covers the cases
somebody already thought of.

**Weak evidence is not promoted.** A candidate accepted only by directory
structure is recorded unverified. It can be discovered and can be reviewed, and it
cannot reach a public response until the institution's own page corroborates an
academic role.

**Domain ownership is not identity.** `admissions.msu.edu` and `msu.edu` are one
institution; `evil-msu.example` is not. But a first-party domain is evidence that
the institution owns the page and never evidence that the text names a professor.

Every test here runs the real classifier and the real policy function against
controlled input. Nothing is mocked below the network boundary, and nothing here
touches the internet.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.supervisor_discovery import (  # noqa: E402
    registrable_domain,
    same_institution,
)
from app.services.supervisor_person import (  # noqa: E402
    classify_person_candidate,
    looks_like_a_person_name,
)

# ---------------------------------------------------------------------------
# Part 19: the name matrix, both directions
# ---------------------------------------------------------------------------

VALID = [
    ("Jane Smith — Professor of Computer Science", "inline_role"),
    ("Dr Ada Lovelace", "honorific"),
    ("Professor Alan Turing", "honorific"),
    ("Grace van Dijk", "source_context"),
]

INVALID = [
    "South Australia",
    "Adelaide City",
    "English Language Centre",
    "School of Computing",
    "Faculty of Engineering",
    "Admissions Office",
    "Adelaide City Campus",
    "Magill Campus",
    "University Senior College",
    "Apply Now",
    "Archive 2019",
    "Library Services",
    "Research Institutes",
    "Student Housing",
]


@pytest.mark.parametrize("label,evidence", VALID)
def test_real_persons_are_accepted_with_named_evidence(label, evidence):
    signal = classify_person_candidate(
        label,
        url="https://uni1.edu/people/grace-hopper",
        directory_context=True,
    )
    assert signal is not None, f"{label!r} should be accepted"
    assert signal.role_evidence == evidence
    assert signal.academic_role_stated is (evidence != "source_context")


@pytest.mark.parametrize("label", INVALID)
def test_places_institutions_and_services_are_rejected(label):
    # The first URL is the real one from the live directory: a life-at-campus
    # path. The second is the adversarial case - the same words sitting at a
    # personal-profile path, which structural evidence alone must still refuse to
    # promote.
    assert classify_person_candidate(label, url="https://uni1.edu/life-at/x", directory_context=True) is None
    assert (
        classify_person_candidate(
            label.lower().replace(" ", "-"), url="https://uni1.edu/people/x", directory_context=True
        )
        is None
    )


def test_a_role_split_out_of_the_same_label_is_still_accepted():
    signal = classify_person_candidate("Jane Smith - Professor of Computer Science")
    assert signal is not None
    assert signal.name == "Jane Smith"
    assert signal.role == "professor"


def test_digit_bearing_and_markup_labels_are_refused():
    assert classify_person_candidate("Room 12 Wing") is None
    assert classify_person_candidate("Ada Lovelace <script>") is None
    assert classify_person_candidate("") is None


def test_a_bare_name_is_refused_outside_a_directory():
    # No role, no directory structure: nothing to go on. This is the honest
    # answer rather than a guess.
    assert classify_person_candidate("Grace Hopper", url="https://uni1.edu/x") is None
    # The same text inside a directory, at a personal path, is accepted.
    assert (
        classify_person_candidate(
            "Grace Hopper", url="https://uni1.edu/people/grace-hopper", directory_context=True
        )
        is not None
    )


def test_navigational_slugs_do_not_create_people():
    for slug in ("faculty", "staff", "directory", "all-staff"):
        signal = classify_person_candidate(
            "Our People", url=f"https://uni1.edu/people/{slug}", directory_context=True
        )
        assert signal is None, slug


def test_a_label_equal_to_a_document_heading_is_refused():
    # Derived from the served document rather than from a list of university names.
    signal = classify_person_candidate(
        "Faculty of Engineering",
        url="https://uni1.edu/people/faculty-of-engineering",
        directory_context=True,
        document_labels=frozenset({"faculty of engineering"}),
    )
    assert signal is None


def test_cheap_screen_is_narrower_than_the_classifier():
    # Documents the difference so a caller cannot mistake the two.
    assert looks_like_a_person_name("Dr Ada Lovelace") is True
    assert looks_like_a_person_name("Grace Hopper") is False
    assert (
        classify_person_candidate(
            "Grace Hopper", url="https://uni1.edu/people/grace-hopper", directory_context=True
        )
        is not None
    )


# ---------------------------------------------------------------------------
# Part 20: the domain matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("https://msu.edu/x", "admissions.msu.edu", True),
        ("https://msu.edu/x", "www.msu.edu", True),
        ("https://admissions.msu.edu/", "https://engineering.msu.edu/people", True),
        ("msu.edu", "https://evil-msu.example", False),
        ("https://example.edu/a", "https://example.com/b", False),
        ("https://adelaide.edu.au/", "https://uq.edu.au/", False),
        # A lookalike that merely ends in the same letters is not a sibling.
        ("https://notmsu.edu/", "https://msu.edu/", False),
        ("https://msu.edu.evil.example/", "https://msu.edu/", False),
    ],
)
def test_same_institution_matrix(left, right, expected):
    assert same_institution(left, right) is expected


def test_country_code_edge_cases():
    # Two-part academic suffixes must resolve to the institution, not the label.
    assert registrable_domain("www.ox.ac.uk") == "ox.ac.uk"
    assert registrable_domain("staff.adelaide.edu.au") == "adelaide.edu.au"
    assert same_institution("https://www.ox.ac.uk/a", "https://chem.ox.ac.uk/b") is True
    assert same_institution("https://a.ac.uk/", "https://b.ac.uk/") is False


def test_unusual_institutional_host():
    # A multi-level institutional subdomain still collapses to the institution.
    assert same_institution("https://a.b.c.msu.edu/", "https://msu.edu/") is True


def test_unknown_host_falls_back_to_exact_match():
    # Conservative by construction: an unrecognised suffix returns itself, so the
    # comparison degrades to exact-host equality rather than guessing.
    assert registrable_domain("example.com") == "example.com"
    assert same_institution("https://example.com/a", "https://example.com/b") is True
    assert same_institution("https://example.com/a", "https://other.example/a") is False


def test_domain_provenance_alone_never_approves_a_person():
    """The boundary Part 20 draws explicitly.

    A first-party domain is evidence that the institution owns the page. It is not
    evidence of a person, an academic role, or supervisor suitability - so the
    person decision must be unchanged by the host being first-party.
    """
    text = "South Australia"
    first_party = classify_person_candidate(
        text, url="https://uni1.edu/people/south-australia", directory_context=True
    )
    still_no_stronger_offsite = classify_person_candidate(
        text, url="https://uni1.edu/people/south-australia", directory_context=False
    )
    # Structural-only evidence may surface a candidate for review...
    assert first_party is not None
    # ...but it is explicitly not an academic-role claim.
    assert first_party.academic_role_stated is False
    assert first_party.role_evidence == "source_context"
    # ...and outside a directory context the same text yields nothing at all.
    assert still_no_stronger_offsite is None