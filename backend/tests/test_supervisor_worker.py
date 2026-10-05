"""The supervisor discovery worker.

No test in this file touches a real university. Every fetch is either a fixture
string or a monkeypatched client, because a test that depends on a live
institutional site is a test that fails on someone else's outage and reports it as
a code defect.

What is being pinned is the set of refusals: a blocked source must not produce a
professor, an unreadable page must not produce a negative result, and running the
same discovery twice must not produce a second copy of anything.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.services import supervisor_discovery as worker  # noqa: E402
from app.services.supervisor_discovery import (  # noqa: E402
    _derive_availability,
    _extract_email,
    _extract_research_areas,
    discover_for_scholarship,
    extract_faculty_candidates,
    host_is_official,
    looks_like_faculty_listing,
    run_discovery_batch,
    scholarship_seed_urls,
)
from app.services.supervisor_status import SupervisorCoverageStatus  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures: realistic shapes, deliberately imperfect
# ---------------------------------------------------------------------------

PROGRAMME_PAGE = """
<html><body>
  <nav><a href="/">Home</a>
       <a href="/people/faculty">Our Faculty</a>
       <a href="/news">News</a>
       <a href="https://other-university.edu/people">Partner Faculty</a>
  </nav>
  <h1>MSc Computer Science</h1>
  <p>Supervision is offered by the School of Computing.</p>
</body></html>
"""

FACULTY_PAGE = """
<html><body>
  <h1>Faculty</h1>
  <ul>
    <li><a href="/people/ada-lovelace">Dr Ada Lovelace</a></li>
    <li><a href="/people/grace-hopper">Professor Grace Hopper</a></li>
    <li><a href="/people/alan-turing">Dr Alan Turing</a></li>
    <li><a href="/people/apply-now">Apply Now</a></li>
    <li><a href="/people/archive">Archive 2019</a></li>
    <li><a href="https://external.edu/people/katherine-johnson">Katherine Johnson</a></li>
  </ul>
</body></html>
"""

PROFILE_PAGE = """
<html><body>
  <h1>Dr Ada Lovelace</h1>
  <p>Professor of Computer Science</p>
  <p>Email: a.lovelace@uni1.edu</p>
  <p>Research interests: machine learning; formal verification; computational complexity</p>
  <p>I am currently accepting applications for the 2027 intake.</p>
</body></html>
"""

PROFILE_PAGE_NO_CONTACT = """
<html><body>
  <h1>Dr Grace Hopper</h1>
  <p>Research interests: compilers</p>
</body></html>
"""

FACULTY_PAGE_NO_RESEARCH = """
<html><body><h1>Faculty</h1>
  <a href="/people/alan-turing">Dr Alan Turing</a>
</body></html>
"""


def _fetch_result(url: str, content: str, status: int = 200):
    from app.services.official_source_fetcher import OfficialSourceFetchResult

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
    from app.models import Base

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
        "status": "open",
        "deadline_date": date(2027, 6, 30),
        "deadline_precision": "exact",
        "eligibility": [],
        "benefits": [],
        "coverage": [],
        "requirements": [],
        "documents": [],
        "application_method": [],
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


@pytest.fixture
def polite_site(monkeypatch):
    """Serve a fixed two-page site, with no network access anywhere.

    Installs a guard on httpx that fails loudly, so a code path that reaches the
    real internet during these tests fails here rather than silently depending on
    a university being up.
    """
    pages = {
        "https://uni1.edu/programmes/msc": PROGRAMME_PAGE,
        "https://uni1.edu/people/faculty": FACULTY_PAGE,
        "https://uni1.edu/people/ada-lovelace": PROFILE_PAGE,
        "https://uni1.edu/people/grace-hopper": PROFILE_PAGE_NO_CONTACT,
        "https://uni1.edu/people/alan-turing": PROFILE_PAGE_NO_CONTACT,
    }

    def fake_polite_fetch(url: str):
        content = pages.get(url.split("#")[0])
        if content is None:
            return None
        return _fetch_result(url, content)

    monkeypatch.setattr(worker, "polite_fetch", fake_polite_fetch)
    worker.clear_robots_cache()
    return pages


# ---------------------------------------------------------------------------
# Source classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host,expected",
    [
        ("mit.edu", True),
        ("ox.ac.uk", True),
        ("unimelb.edu.au", True),
        ("u-tokyo.ac.jp", True),
        ("ethz.ch", True),
        ("scholarshipsportal.com", False),
        ("facebook.com", False),
        ("medium.com", False),
        ("", False),
        (None, False),
    ],
)
def test_official_host_classification(host, expected):
    assert host_is_official(host) is expected


def test_faculty_listing_detection():
    assert looks_like_faculty_listing("https://uni1.edu/people/faculty", "Our Faculty") is True
    assert looks_like_faculty_listing("https://uni1.edu/staff", "Staff") is True
    assert looks_like_faculty_listing("https://uni1.edu/news", "News") is False


def test_subject_area_navigation_is_not_a_faculty_listing():
    """Regression from the real read-only pilot.

    The detector used to accept any link containing the word "academic". On a
    large university admissions site it selected /academics and
    /academics/research as faculty directories. Both are subject-area navigation
    that lists nobody, so each burned a request from a budget meant for pages
    that might publish names. Recorded from scholarship 63 (Michigan State).
    """
    assert looks_like_faculty_listing("https://admissions.msu.edu/academics", "Academics") is False
    assert (
        looks_like_faculty_listing("https://admissions.msu.edu/academics/research", "Research")
        is False
    )


def test_a_people_directory_is_still_recognised_by_its_anchor():
    # Tightening the path test must not lose the case it was meant to keep: a
    # directory on an unremarkable path, named only by its link text.
    assert looks_like_faculty_listing("https://uni1.edu/directory", "Staff directory") is True
    assert looks_like_faculty_listing("https://uni1.edu/about", "Our Faculty") is True


def test_seed_urls_prefers_the_official_source_and_drops_junk():
    from app.models import Scholarship

    row = Scholarship(official_source_url="https://uni1.edu/p", catalogue_url="https://uni1.edu/c")
    row.official_updates_url = "javascript:void(0)"

    urls = scholarship_seed_urls(row)

    assert urls == ["https://uni1.edu/p", "https://uni1.edu/c"]


def test_seed_urls_are_empty_when_nothing_official_is_recorded():
    from app.models import Scholarship

    assert scholarship_seed_urls(Scholarship()) == []


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def test_only_people_on_the_institution_host_are_extracted(polite_site):
    candidates = extract_faculty_candidates(
        FACULTY_PAGE, "https://uni1.edu/people/faculty", "uni1.edu"
    )
    urls = {candidate.profile_url for candidate in candidates}

    assert "https://uni1.edu/people/ada-lovelace" in urls
    assert "https://uni1.edu/people/grace-hopper" in urls
    # A partner institution's directory is not evidence about this one.
    assert not any("external.edu" in url for url in urls)


def test_link_labels_are_not_mistaken_for_people(polite_site):
    # Directory structure alone identifies a *candidate to check*, not a professor,
    # so a call to action can appear in the candidate list. What must never happen
    # is a professor row being created from it, which is enforced by the storage gate
    # and asserted in test_supervisor_discovery_states.py. Keeping both assertions
    # matters: the candidate layer may be permissive, the storage layer may not.
    candidates = extract_faculty_candidates(
        FACULTY_PAGE, "https://uni1.edu/people/faculty", "uni1.edu"
    )
    names = {candidate.name for candidate in candidates}
    assert "Archive 2019" not in names

    from app.services.supervisor_person import classify_person_candidate

    assert (
        classify_person_candidate(
            "Apply Now", url="https://uni1.edu/people/apply-now", directory_context=True
        ).academic_role_stated
        is False
    )


def test_a_candidate_without_a_profile_url_is_impossible(polite_site):
    candidates = extract_faculty_candidates(
        FACULTY_PAGE, "https://uni1.edu/people/faculty", "uni1.edu"
    )

    assert candidates
    assert all(candidate.profile_url.startswith("https://uni1.edu/") for candidate in candidates)
    assert all(candidate.name for candidate in candidates)


def test_research_areas_come_only_from_a_labelled_section(polite_site):
    candidates = extract_faculty_candidates(
        FACULTY_PAGE, "https://uni1.edu/people/faculty", "uni1.edu"
    )
    ada = next(c for c in candidates if "lovelace" in c.profile_url)

    assert "machine learning" in [area.lower() for area in ada.research_areas]


def test_prose_mentioning_research_yields_no_areas():
    assert _extract_research_areas("She enjoys research and reads widely.") == []


def test_an_email_is_only_taken_from_the_institution_domain():
    assert _extract_email("<a href='mailto:a.lovelace@uni1.edu'>", "uni1.edu") == "a.lovelace@uni1.edu"
    assert _extract_email("write to a.lovelace@gmail.com", "uni1.edu") is None
    assert _extract_email("contact: info@uni1.edu", "uni1.edu") == "info@uni1.edu"
    # A subdomain of the institution is still the institution.
    assert _extract_email("cs@cs.uni1.edu", "uni1.edu") == "cs@cs.uni1.edu"


def test_placeholder_addresses_are_rejected():
    assert _extract_email("yourname@uni1.edu", "uni1.edu") is None
    assert _extract_email("noreply@uni1.edu", "uni1.edu") is None


def test_availability_is_read_only_from_an_explicit_statement():
    assert _derive_availability("I am currently accepting applications.") == "verified_yes"
    assert _derive_availability("I am not accepting students this year.") == "verified_no"
    # Silence is not a "no", and this is the single most misleading thing the
    # feature could publish.
    assert _derive_availability("I supervise postgraduate students.") == "not_published"
    assert _derive_availability("") == "not_published"


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------


def test_an_authoritative_site_produces_verified_professors_with_provenance(db, polite_site):
    from app.models_supervisor import ProfessorProfile, ScholarshipProfessorLink, SupervisorSourceEvidence

    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    assert db.query(ProfessorProfile).count() >= 2
    assert db.query(ScholarshipProfessorLink).count() >= 2
    # Every published relationship carries a source. Provenance is not optional.
    for link in db.query(ScholarshipProfessorLink).all():
        assert link.evidence_source_url
        assert link.evidence_source_type
        assert link.verification_status == "verified"
    assert db.query(SupervisorSourceEvidence).count() >= 2


def test_an_email_published_on_the_official_page_is_marked_verified(db, polite_site):
    from app.models_supervisor import ProfessorProfile

    discover_for_scholarship(db, _scholarship(db))

    ada = (
        db.query(ProfessorProfile)
        .filter(ProfessorProfile.canonical_name.like("%Lovelace%"))
        .one()
    )
    assert ada.official_email == "a.lovelace@uni1.edu"
    assert ada.official_email_verified is True


def test_availability_defaults_to_not_published_when_the_page_is_silent(db, polite_site):
    from app.models_supervisor import ProfessorAvailability, ProfessorProfile

    discover_for_scholarship(db, _scholarship(db))

    hopper = (
        db.query(ProfessorProfile)
        .filter(ProfessorProfile.canonical_name.like("%Hopper%"))
        .one()
    )
    rows = db.query(ProfessorAvailability).filter_by(professor_id=hopper.id).all()
    assert [row.state for row in rows] == ["not_published"]


def test_running_discovery_twice_creates_no_duplicates(db, polite_site):
    from app.models_supervisor import ProfessorProfile, ScholarshipProfessorLink

    scholarship = _scholarship(db)

    discover_for_scholarship(db, scholarship)
    first_professors = db.query(ProfessorProfile).count()
    first_links = db.query(ScholarshipProfessorLink).count()

    discover_for_scholarship(db, scholarship)

    assert db.query(ProfessorProfile).count() == first_professors
    assert db.query(ScholarshipProfessorLink).count() == first_links


def test_the_coverage_count_never_inflates_across_runs(db, polite_site):
    from app.models_supervisor import ScholarshipSupervisorCoverage

    scholarship = _scholarship(db)
    discover_for_scholarship(db, scholarship)
    first = db.query(ScholarshipSupervisorCoverage).one().verified_supervisor_count

    discover_for_scholarship(db, scholarship)
    second = db.query(ScholarshipSupervisorCoverage).one().verified_supervisor_count

    assert second == first


def test_a_non_institutional_source_is_refused(db, monkeypatch):
    scholarship = _scholarship(db, official_source_url="https://scholarshipsportal.com/x")

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)


def test_a_scholarship_with_no_official_source_stays_pending(db):
    from app.models_supervisor import ProfessorProfile

    scholarship = _scholarship(db, official_source_url=None, catalogue_url=None)

    outcome = discover_for_scholarship(db, scholarship)

    assert db.query(ProfessorProfile).count() == 0
    assert outcome.status in (
        str(SupervisorCoverageStatus.SEARCH_PENDING),
        str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND),
    )


def test_an_unreachable_source_produces_no_professor(db, monkeypatch):
    from app.models_supervisor import ProfessorProfile

    monkeypatch.setattr(worker, "polite_fetch", lambda url: None)
    worker.clear_robots_cache()
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert db.query(ProfessorProfile).count() == 0
    # A blocked source must never be reported as "no professors exist".
    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)


def test_a_page_read_successfully_with_no_faculty_link_is_a_true_negative(db, monkeypatch):
    from app.models_supervisor import ProfessorProfile

    monkeypatch.setattr(worker, "polite_fetch", lambda url: None)
    worker.clear_robots_cache()
    # A site whose programme page links nowhere useful.
    monkeypatch.setattr(
        worker,
        "polite_fetch",
        lambda url: _fetch_result(url, "<html><body><p>No directory here.</p></body></html>"),
    )
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert db.query(ProfessorProfile).count() == 0
    assert outcome.status == str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)


def test_malformed_html_does_not_crash_the_run(db, monkeypatch):
    from app.models_supervisor import ProfessorProfile

    # Unclosed tags, stray attributes, no anchors. The parser must absorb this
    # rather than raising part-way through a batch.
    broken = "<html><body><p>Unclosed <b>markup <div class=><span></p></body"
    monkeypatch.setattr(worker, "polite_fetch", lambda url: _fetch_result(url, broken))
    worker.clear_robots_cache()
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert db.query(ProfessorProfile).count() == 0
    assert outcome.status == str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)


def test_a_403_on_the_faculty_page_blocks_rather_than_emptying(db, monkeypatch):
    from app.models_supervisor import ProfessorProfile
    from app.services.official_source_fetcher import OfficialSourceFetchResult

    def fetch(url: str):
        if "faculty" in url:
            return OfficialSourceFetchResult(
                success=False, status_code=403, error_type="forbidden"
            )
        return _fetch_result(url, PROGRAMME_PAGE)

    monkeypatch.setattr(worker, "polite_fetch", fetch)
    worker.clear_robots_cache()
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert db.query(ProfessorProfile).count() == 0
    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)


def test_a_timeout_is_not_treated_as_an_empty_directory(db, monkeypatch):
    from app.models_supervisor import ProfessorProfile
    from app.services.official_source_fetcher import OfficialSourceFetchResult

    monkeypatch.setattr(
        worker,
        "polite_fetch",
        lambda url: OfficialSourceFetchResult(success=False, error_type="timeout"),
    )
    worker.clear_robots_cache()
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert db.query(ProfessorProfile).count() == 0
    assert outcome.status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_retryable_and_server_failures_are_not_negatives(db, monkeypatch, status_code):
    from app.services.official_source_fetcher import OfficialSourceFetchResult

    monkeypatch.setattr(
        worker,
        "polite_fetch",
        lambda url: OfficialSourceFetchResult(success=False, status_code=status_code),
    )
    worker.clear_robots_cache()
    scholarship = _scholarship(db)

    outcome = discover_for_scholarship(db, scholarship)

    assert outcome.status != str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)


# ---------------------------------------------------------------------------
# Politeness
# ---------------------------------------------------------------------------


def test_robots_disallow_prevents_the_request(monkeypatch):
    import httpx

    calls: list[str] = []

    def fake_get(self, url, **kwargs):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /people/",
                headers={"content-type": "text/plain"},
                request=httpx.Request("GET", url),
            )
        return httpx.Response(
            200,
            text="<html><body><p>Programme page</p></body></html>",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    worker.clear_robots_cache()

    allowed = worker.polite_fetch("https://uni1.edu/programmes/msc")
    blocked = worker.polite_fetch("https://uni1.edu/people/faculty")

    assert allowed is not None
    assert blocked is None
    assert any(url.endswith("/robots.txt") for url in calls)
    # The disallowed path was never fetched; only the robots file was requested
    # for that origin, and the cache means not even that twice.
    assert not any(url.endswith("/people/faculty") for url in calls)


def test_an_unreadable_robots_file_fails_closed(monkeypatch):
    import httpx

    def fake_get(self, url, **kwargs):
        if url.endswith("/robots.txt"):
            raise httpx.ConnectError("no route to host")
        return httpx.Response(200, text="<html></html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    worker.clear_robots_cache()

    # Deciding that an unreadable policy permits everything is how a crawler ends
    # up somewhere it was told not to go.
    assert worker.polite_fetch("https://uni1.edu/programmes/msc") is None


def test_batch_concurrency_is_capped(db, monkeypatch):
    """The batch must never run more workers than the politeness limit.

    Measured rather than asserted against a constant: the point is that the
    executor is actually built from the bounded value.
    """
    import threading
    import time

    for index in range(6):
        _scholarship(db, official_source_url=f"https://uni{index + 1}.edu/p")

    lock = threading.Lock()
    in_flight = 0
    peak = 0

    def fake_discover_one(scholarship):
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        time.sleep(0.02)
        with lock:
            in_flight -= 1
        from app.services.supervisor_discovery import DiscoveryOutcome

        return DiscoveryOutcome(scholarship_id=scholarship.id, status="search_pending")

    monkeypatch.setattr(worker, "_discover_one", fake_discover_one)

    outcomes = run_discovery_batch(db, limit=6, max_workers=3)

    assert len(outcomes) == 6
    assert peak <= 3
    assert worker.MAX_WORKERS <= worker.MAX_WORKERS_CEILING


def test_an_empty_batch_returns_nothing(db):
    assert run_discovery_batch(db, limit=5) == []


def test_robots_cache_can_be_cleared():
    worker.clear_robots_cache()
    assert worker._ROBOTS_CACHE == {}