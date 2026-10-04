"""The discovery state machine, against deterministic fixtures.

The invariant these tests exist to protect:

    inability to observe  !=  evidence of absence

Each fixture is one of the ways a real institutional source failed us, captured as
a fixed string so the release gate never depends on a university being reachable.
The network boundary is mocked; the extractor, the person classifier and the state
machine all run for real.

The matrix:

===========================================  ===================================
fixture                                      expected state
===========================================  ===================================
genuine faculty page with a stated role      FOUND, verified
server-rendered directory, nobody listed     verified negative
place-name directory, no person qualifies    verified negative
empty shell                                  SOURCE_REQUIRES_RENDERING
JavaScript-rendered shell                    SOURCE_REQUIRES_RENDERING
login-gated directory                        SOURCE_BLOCKED
unreachable source                           SOURCE_BLOCKED
served a directory with no role evidence     found, unverified
===========================================  ===================================
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
)
from app.services import supervisor_discovery as worker  # noqa: E402
from app.services.official_source_fetcher import OfficialSourceFetchResult  # noqa: E402
from app.services.supervisor_discovery import (  # noqa: E402
    discover_for_scholarship,
    page_requires_authentication,
)
from app.services.supervisor_status import (  # noqa: E402
    INCONCLUSIVE_COVERAGE_STATUSES,
    PUBLIC_RELATIONSHIP_STATUSES,
    RelationshipVerificationStatus,
    SupervisorCoverageStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROGRAMME_PAGE = (
    '<html><body><nav>'
    '<a href="/people/faculty">Our Faculty</a>'
    "</nav><h1>MSc Computer Science</h1></body></html>"
)

#: A genuine directory: people named, with an academic role stated, each linking to
#: a personal profile on the institution's own host.
GENUINE_FACULTY_PAGE = """
<html><body>
  <h1>Faculty of Computing</h1>
  <ul>
    <li><a href="/people/ada-lovelace">Dr Ada Lovelace</a></li>
    <li><a href="/people/alan-turing">Professor Alan Turing</a></li>
    <li><a href="/people/grace-hopper">Dr Grace Hopper</a></li>
  </ul>
</body></html>
"""

PROFILE_PAGE = """
<html><body>
  <h1>Dr Ada Lovelace</h1>
  <p>Professor of Computer Science</p>
  <p>Email: a.lovelace@uni1.edu</p>
  <p>Research interests: machine learning; formal verification</p>
  <p>I am currently accepting applications for the 2027 intake.</p>
</body></html>
"""

#: Read successfully, server-rendered, and lists nobody. This IS a true negative.
EMPTY_DIRECTORY = (
    "<html><body><h1>Faculty of Computing</h1>"
    "<p>No academic staff are listed in this section.</p>"
    "<p>The faculty group is currently being restructured.</p></body></html>"
) * 40

#: The real Adelaide shape: place and campus names presented in person-shaped
#: markup, none of which is anybody.
PLACE_NAME_DIRECTORY = """
<html><body>
  <h1>Our People</h1>
  <ul>
    <li><a href="/life-at-adelaide/adelaide-and-south-australia/south-australia/">South Australia</a></li>
    <li><a href="/life-at-adelaide/adelaide-and-south-australia/adelaide-city/">Adelaide City</a></li>
    <li><a href="/life-at-adelaide/campuses/magill-campus/">Magill Campus</a></li>
    <li><a href="/study/english-language-centre/">English Language Centre</a></li>
    <li><a href="/about/university-senior-college/">University Senior College</a></li>
  </ul>
</body></html>
"""

#: The real Adelaide/Erasmus shape: a document that is almost entirely script.
JS_SHELL_DIRECTORY = (
    "<html><head><title>People</title></head><body>"
    + "<script>window.__APP__={config:{}};</script>" * 900
    + '<div id="root"></div></body></html>'
)

#: Empty but server-rendered: a real document with nothing in it.
EMPTY_SHELL_DIRECTORY = "<html><body></body></html>" * 400

#: The real Michigan State shape: the people search resolves to a sign-in page.
LOGIN_GATED_DIRECTORY = """
<html><head><title>Michigan State University - Sign In</title></head>
<body><h1>Sign in to search people</h1>
<form action="/login" method="post">
  <input type="text" name="username"/>
  <input type="password" name="password"/>
  <button>Sign In</button>
</form></body></html>
"""

#: A directory of personal profile links where no role is stated anywhere - not in
#: the listing and not on the profile. The candidates are people by structure and
#: by name shape, and that is the whole of the evidence.
ROLELESS_DIRECTORY = """
<html><body>
  <h1>Academic Staff</h1>
  <ul>
    <li><a href="/people/ada-lovelace">Ada Lovelace</a></li>
    <li><a href="/people/alan-turing">Alan Turing</a></li>
  </ul>
</body></html>
"""

#: The profile for that directory: a real page about a real person, which simply
#: never states an academic rank.
ROLELESS_PROFILE_PAGE = """
<html><body>
  <h1>Ada Lovelace</h1>
  <p>Analytical Engine project, notes and correspondence.</p>
  <p>Email: a.lovelace@uni1.edu</p>
  <p>Research interests: machine learning</p>
</body></html>
"""


def _fetch(url: str, content: str, status: int = 200) -> OfficialSourceFetchResult:
    return OfficialSourceFetchResult(
        success=True,
        status_code=status,
        final_url=url,
        content=content,
        content_type="text/html",
    )


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _scholarship(db, **overrides):
    from app.models import Scholarship

    base = {
        "title": "MSc Computer Science",
        "country": "United Kingdom",
        "degree": "Master",
        "funding": "Fully Funded",
        "description": "A test programme record.",
        "status": "open",
        "deadline_date": date(2027, 6, 30),
        "deadline_precision": "exact",
        "eligibility": [],
        "coverage": [],
        "requirements": [],
        "documents": [],
        "official_source": "Test University",
        "official_source_url": "https://uni1.edu/programmes/msc",
        "is_verified": True,
        "verification_status": "active",
        "image_url": "https://uni1.edu/logo.png",
    }
    base.update(overrides)
    row = Scholarship(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _serve(monkeypatch, directory_html: str, *, profile_html: str = PROFILE_PAGE):
    """Mock only the network boundary; every policy function still runs."""

    def fake_fetch(url: str):
        if "/people/faculty" in url:
            return _fetch(url, directory_html)
        if "/people/" in url:
            return _fetch(url, profile_html)
        return _fetch(url, PROGRAMME_PAGE)

    monkeypatch.setattr(worker, "polite_fetch", fake_fetch)
    worker.clear_robots_cache()


def _status(db, scholarship_id: int) -> str:
    return db.query(ScholarshipSupervisorCoverage).one().status


# ---------------------------------------------------------------------------
# FOUND
# ---------------------------------------------------------------------------


def test_a_genuine_faculty_directory_yields_verified_professors(monkeypatch, db):
    _serve(monkeypatch, GENUINE_FACULTY_PAGE)
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    links = db.query(ScholarshipProfessorLink).all()
    assert len(links) == 3
    assert all(link.verification_status in PUBLIC_RELATIONSHIP_STATUSES for link in links)
    # Provenance is mandatory on every published relationship.
    assert all(link.evidence_source_url and link.evidence_source_type for link in links)
    # And the email was published on the profile, so it is recorded as verified.
    from app.models_supervisor import ProfessorProfile

    ada = (
        db.query(ProfessorProfile)
        .filter(ProfessorProfile.canonical_name.like("%Lovelace%"))
        .one()
    )
    assert ada.official_email == "a.lovelace@uni1.edu"
    assert ada.official_email_verified is True


def test_structural_only_evidence_never_becomes_a_professor_row(monkeypatch, db):
    """The strongest guarantee in this file.

    Directory structure plus a name-shaped label is not enough. With no academic
    role stated on the listing or on the profile, no professor row is created at
    all - not created and then hidden, not created as unverified. A record is a
    claim, and a claim needs a role behind it.
    """
    _serve(monkeypatch, ROLELESS_DIRECTORY, profile_html=ROLELESS_PROFILE_PAGE)
    scholarship = _scholarship(db)

    discover_for_scholarship(db, scholarship)

    from app.models_supervisor import ProfessorProfile

    assert db.query(ProfessorProfile).count() == 0
    assert db.query(ScholarshipProfessorLink).count() == 0


def test_a_role_on_the_profile_promotes_a_structural_candidate(monkeypatch, db):
    # The complementary case: the listing gave only structure, the profile states the
    # role. That is evidence, and it is enough to publish.
    _serve(monkeypatch, ROLELESS_DIRECTORY, profile_html=PROFILE_PAGE)
    scholarship = _scholarship(db)

    discover_for_scholarship(db, scholarship)

    links = db.query(ScholarshipProfessorLink).all()
    assert len(links) == 2
    assert all(link.verification_status in PUBLIC_RELATIONSHIP_STATUSES for link in links)


# ---------------------------------------------------------------------------
# Verified negatives
# ---------------------------------------------------------------------------


def test_a_read_directory_listing_nobody_is_a_verified_negative(monkeypatch, db):
    _serve(monkeypatch, EMPTY_DIRECTORY)
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
    assert _status(db, scholarship.id) == str(
        SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND
    )


def test_a_place_name_directory_creates_no_professor(monkeypatch, db):
    """The real Adelaide failure mode, as a fixture.

    Every link looks like a person entry and none is one. Nothing may be stored,
    and the outcome is a true negative only because the page was genuinely read.
    """
    _serve(monkeypatch, PLACE_NAME_DIRECTORY)
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    from app.models_supervisor import ProfessorProfile

    assert db.query(ProfessorProfile).count() == 0
    assert db.query(ScholarshipProfessorLink).count() == 0
    assert outcome.professors_found == 0
    assert outcome.status == str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)


# ---------------------------------------------------------------------------
# Inconclusive: must never become a negative
# ---------------------------------------------------------------------------


def test_a_javascript_rendered_directory_requires_rendering(monkeypatch, db):
    _serve(monkeypatch, JS_SHELL_DIRECTORY)
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING)
    assert outcome.status != str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
    assert outcome.status in INCONCLUSIVE_COVERAGE_STATUSES


def test_an_empty_shell_requires_rendering_and_is_not_a_negative(monkeypatch, db):
    _serve(monkeypatch, EMPTY_SHELL_DIRECTORY)
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING)


def test_a_login_gated_directory_is_inaccessible_and_not_a_negative(monkeypatch, db):
    _serve(monkeypatch, LOGIN_GATED_DIRECTORY)
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)
    assert outcome.status != str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
    assert outcome.status in INCONCLUSIVE_COVERAGE_STATUSES


def test_an_unreachable_source_is_blocked_and_not_a_negative(monkeypatch, db):
    monkeypatch.setattr(worker, "polite_fetch", lambda url: None)
    worker.clear_robots_cache()
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)
    assert outcome.status != str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)


@pytest.mark.parametrize(
    "status_code", [403, 404, 429, 500, 503]
)
def test_no_http_failure_is_ever_read_as_a_negative(monkeypatch, db, status_code):
    monkeypatch.setattr(
        worker,
        "polite_fetch",
        lambda url: OfficialSourceFetchResult(success=False, status_code=status_code),
    )
    worker.clear_robots_cache()
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status != str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
    assert outcome.status in INCONCLUSIVE_COVERAGE_STATUSES


# ---------------------------------------------------------------------------
# The login detector itself
# ---------------------------------------------------------------------------


def test_login_gated_detection():
    assert page_requires_authentication(LOGIN_GATED_DIRECTORY) is True
    assert page_requires_authentication(GENUINE_FACULTY_PAGE) is False
    assert page_requires_authentication(JS_SHELL_DIRECTORY) is False
    assert page_requires_authentication("") is False


def test_every_state_is_distinct_and_serialisable():
    from app.services.supervisor_status import SupervisorCoverageStatus as S

    values = {str(member.value) for member in S}
    assert "source_requires_rendering" in values
    # The state is a plain string value, so it survives JSON round-tripping.
    import json

    assert json.loads(json.dumps({"s": str(S.SOURCE_REQUIRES_RENDERING)}))["s"] == (
        "source_requires_rendering"
    )
    assert str(S.SOURCE_REQUIRES_RENDERING) != str(S.NO_VERIFIED_SUPERVISOR_FOUND)
    assert str(S.SOURCE_REQUIRES_RENDERING) in INCONCLUSIVE_COVERAGE_STATUSES
    assert str(S.NO_VERIFIED_SUPERVISOR_FOUND) not in INCONCLUSIVE_COVERAGE_STATUSES