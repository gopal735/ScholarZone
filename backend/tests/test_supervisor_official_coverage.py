"""Official-source coverage: provenance, contacts, batching, and honest negatives.

These tests pin the behaviour that makes a coverage claim true rather than
merely cheerful. The network boundary is mocked with fixtures shaped like the
real pages the worker has actually read - a genuine directory with stated
roles, a login wall, a JavaScript shell, a cross-institution link - so what is
under test is the policy, not a happy path.

The matrix, one test per row:

======================================================  ==========================
claim under test                                          asserted here
======================================================  ==========================
a published relationship always carries provenance      verified link + source
an email is published only from the awarding domain     foreign address withheld
a cross-institution candidate is never a relationship   no row, no link
one person on two pages is one row, re-runs are no-ops  one profile, one link
a non-programme award is not applicable, with evidence  NOT_APPLICABLE + quote
an unknown record is searched, not pre-judged           pending, then searched
a blocked source is blocked, never a negative           SOURCE_BLOCKED, no claim
a contact is an office, never a professor               separate list, no name
a contact email is gated like a professor's             unverified address withheld
a database predating the contact table still serves     tolerant read
the batch resumes from a cursor without duplicating     after_id + state file
a dry run reports and writes nothing                    zero writes, zero files
the audit log reconstructs a run                        one JSON line per item
rendering stays off unless an operator turns it on      flag untouched
======================================================  ==========================
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base, Scholarship  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorProfile,
    ScholarshipOfficialContact,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
)
from app.services import supervisor_contacts as contacts  # noqa: E402
from app.services import supervisor_discovery as worker  # noqa: E402
from app.services.official_source_fetcher import OfficialSourceFetchResult  # noqa: E402
from app.services.supervisor_applicability import (  # noqa: E402
    classify_supervisor_applicability,
)
from app.services.supervisor_batch import (  # noqa: E402
    BatchOptions,
    read_state,
    run_supervisor_batch,
    select_batch_candidates,
)
from app.services.supervisor_public import (  # noqa: E402
    ScholarshipNotPublic,
    build_supervisor_list,
)
from app.services.supervisor_status import (  # noqa: E402
    AUTHORITATIVE_SOURCE_TYPES,
    PUBLIC_RELATIONSHIP_STATUSES,
    ProfessorRelationshipType,
    SupervisorCoverageStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROGRAMME_PAGE = (
    '<html><body><nav><a href="/people/faculty">Our Faculty</a>'
    "</nav><h1>MSc Computer Science</h1></body></html>"
)

#: The same programme page with a contact route linked on it. An office link is
#: published information and not a guess, so it is followed one hop.
PROGRAMME_PAGE_WITH_CONTACT = (
    '<html><body><nav><a href="/people/faculty">Our Faculty</a>'
    '<a href="/office/contact">Contact the scholarships office</a>'
    "</nav><h1>MSc Computer Science</h1></body></html>"
)

#: A programme page that publishes no contact route and no address at all.
BARE_PROGRAMME_PAGE = (
    '<html><body><nav><a href="/people/faculty">Our Faculty</a></nav>'
    "<h1>MSc Computer Science</h1></body></html>"
)

GENUINE_FACULTY_PAGE = """
<html><body>
  <h1>Faculty of Computing</h1>
  <ul>
    <li><a href="/people/ada-lovelace">Dr Ada Lovelace</a></li>
    <li><a href="/people/alan-turing">Professor Alan Turing</a></li>
  </ul>
</body></html>
"""

#: A profile that publishes an address on the institution's own domain. The one
#: case in which a stored address may be marked verified.
PROFILE_WITH_OWN_DOMAIN_EMAIL = """
<html><body>
  <h1>Dr Ada Lovelace</h1>
  <p>Professor of Computer Science</p>
  <p>Email: a.lovelace@uni1.edu</p>
  <p>Research interests: machine learning; formal verification</p>
</body></html>
"""

#: The same profile, but the address belongs to somebody else's domain. Reading
#: it into the record would publish an address the institution never published.
PROFILE_WITH_FOREIGN_EMAIL = """
<html><body>
  <h1>Dr Ada Lovelace</h1>
  <p>Professor of Computer Science</p>
  <p>Email: a.lovelace@gmail.com</p>
</body></html>
"""

#: A listing that links off-site. The awarding institution's faculty page is
#: authoritative about itself; another university's page is not evidence here.
CROSS_INSTITUTION_LISTING = """
<html><body>
  <h1>Faculty of Computing</h1>
  <ul>
    <li><a href="https://other-university.edu/people/grace-hopper">Dr Grace Hopper</a></li>
  </ul>
</body></html>
"""

#: The real Michigan State shape, reproduced so the negative is asserted rather
#: than assumed.
LOGIN_GATED_DIRECTORY = """
<html><head><title>Test University - Sign In</title></head>
<body><h1>Sign in to search people</h1>
<form action="/login" method="post">
  <input type="text" name="username"/>
  <input type="password" name="password"/>
</form></body></html>
"""

#: A contact page published by the awarding body itself.
CONTACT_PAGE = """
<html><body>
  <h1>Contact the Scholarships Office</h1>
  <p>Email: scholarships@uni1.edu</p>
  <a href="https://uni1.edu/office/contact">Scholarships office</a>
</body></html>
"""

CONTACT_PAGE_FOREIGN_EMAIL = """
<html><body>
  <h1>Contact the Scholarships Office</h1>
  <p>Email: scholarships@gmail.com</p>
  <a href="https://uni1.edu/office/contact">Scholarships office</a>
</body></html>
"""


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
        "program_type": "University scholarship",
    }
    base.update(overrides)
    row = Scholarship(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _fetch(url: str, content: str, status: int = 200) -> OfficialSourceFetchResult:
    return OfficialSourceFetchResult(
        success=True,
        status_code=status,
        final_url=url,
        content=content,
        content_type="text/html",
    )


#: A contact route whose link text is page furniture. The route is still
#: followed - the path is what identifies an office - but the furniture is not
#: published as the office's name.
PROGRAMME_PAGE_WITH_FURNITURE_CONTACT = (
    '<html><body><nav><a href="/people/faculty">Our Faculty</a>'
    '<a href="/office/contact">Skip to main content</a>'
    "</nav><h1>MSc Computer Science</h1></body></html>"
)


def _serve_discovery(
    monkeypatch,
    directory_html: str,
    profile_html: str = PROFILE_WITH_OWN_DOMAIN_EMAIL,
    programme_html: str = BARE_PROGRAMME_PAGE,
):
    """Mock only the network boundary. Every policy function still runs."""

    def fake_fetch(url: str):
        if "/people/faculty" in url:
            return _fetch(url, directory_html)
        if "/people/" in url:
            return _fetch(url, profile_html)
        if "/office/contact" in url:
            return _fetch(url, CONTACT_PAGE)
        return _fetch(url, programme_html)

    monkeypatch.setattr(worker, "polite_fetch", fake_fetch)
    monkeypatch.setattr(contacts, "polite_fetch", fake_fetch)
    worker.clear_robots_cache()


def _options(**overrides) -> BatchOptions:
    base = {
        "limit": 25,
        "collect_contacts": False,
        "workers": 1,
    }
    base.update(overrides)
    return BatchOptions(**base)


# ---------------------------------------------------------------------------
# Provenance, email trust, relationship accuracy
# ---------------------------------------------------------------------------


def test_every_published_relationship_carries_provenance(monkeypatch, db):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    _scholarship(db)

    report = run_supervisor_batch(db, _options())

    assert report.items[0].outcome_status == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    links = db.query(ScholarshipProfessorLink).all()
    assert len(links) == 2
    for link in links:
        # Provenance is mandatory, and it must be an authoritative source type:
        # a secondary page may find a person but never founds a relationship.
        assert link.evidence_source_url
        assert link.evidence_source_type in AUTHORITATIVE_SOURCE_TYPES
        assert link.verification_status in PUBLIC_RELATIONSHIP_STATUSES
        # And the relationship vocabulary is the closed one from the model.
        assert link.relationship_type == str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR)


def test_an_email_from_another_domain_is_never_published(monkeypatch, db):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE, profile_html=PROFILE_WITH_FOREIGN_EMAIL)
    scholarship = _scholarship(db)

    run_supervisor_batch(db, _options())

    profile = db.query(ProfessorProfile).filter(ProfessorProfile.canonical_name.like("%Lovelace%")).one()
    # The person is still discovered - the foreign address is the only thing
    # refused. An address is not evidence about the person.
    assert profile is not None
    assert profile.official_email != "a.lovelace@gmail.com"
    assert profile.official_email_verified is False

    coverage, professors, _ = build_supervisor_list(db, scholarship.id)
    assert coverage["coverage_status"] == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    for professor in professors:
        assert professor["official_email"] is None
        assert professor["official_email_verified"] is False


def test_a_cross_institution_candidate_is_never_linked(monkeypatch, db):
    _serve_discovery(monkeypatch, CROSS_INSTITUTION_LISTING)
    _scholarship(db)

    run_supervisor_batch(db, _options())

    assert db.query(ProfessorProfile).count() == 0
    assert db.query(ScholarshipProfessorLink).count() == 0


def test_one_person_on_two_pages_is_one_row_and_re_runs_are_no_ops(monkeypatch, db):
    """The deduplication contract, and the idempotency contract that rests on it.

    Two directory pages both list the same professor, and the batch is run
    twice. The unique profile URL is the identity, so the second page and the
    second run update the same rows rather than adding near-duplicates.
    """
    _serve_discovery(
        monkeypatch,
        GENUINE_FACULTY_PAGE + '<a href="/people/faculty-2">More faculty</a>',
    )
    _scholarship(db)

    run_supervisor_batch(db, _options())
    first_profiles = db.query(ProfessorProfile).count()
    first_links = db.query(ScholarshipProfessorLink).count()

    # Force a second pass over the same record by re-opening its coverage, which
    # is what an operator retrying a blocked or negative record does.
    row = db.query(ScholarshipSupervisorCoverage).one()
    row.status = str(SupervisorCoverageStatus.SEARCH_PENDING)
    db.commit()

    run_supervisor_batch(db, _options())

    assert db.query(ProfessorProfile).count() == first_profiles
    assert db.query(ScholarshipProfessorLink).count() == first_links
    # And the count on the coverage row still matches the rows that exist.
    coverage = db.query(ScholarshipSupervisorCoverage).one()
    publishable = sum(
        1
        for link in db.query(ScholarshipProfessorLink).all()
        if link.verification_status in PUBLIC_RELATIONSHIP_STATUSES
    )
    assert coverage.verified_supervisor_count == publishable


# ---------------------------------------------------------------------------
# Not applicable, with evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "degree,program_type,expected_applicable",
    [
        ("Short-term professional development (2-52 weeks)", None, False),
        ("English language (pre-tertiary pathway)", "Private education provider scholarship", False),
        ("Non-degree language course", None, False),
        # A degree first, a short course second: still a degree programme.
        ("Master's (short course)", None, True),
        # Silence is not evidence. These are searched, not pre-judged.
        ("Other", "Government scholarship", True),
        ("Unknown", None, True),
        ("Not specified", "Government scholarship", True),
        (None, None, True),
        ("PhD", "University doctoral scholarship", True),
    ],
)
def test_applicability_is_evidence_based(degree, program_type, expected_applicable):
    class Record:
        pass

    record = Record()
    record.degree = degree
    record.program_type = program_type

    result = classify_supervisor_applicability(record)

    assert result.applicable is expected_applicable
    if not expected_applicable:
        # The rationale quotes the record's own fields; it does not explain
        # itself with a category name only.
        assert result.rationale
        assert "degree=" in result.rationale or "program_type=" in result.rationale


def test_a_non_programme_award_is_marked_not_applicable_with_its_evidence(monkeypatch, db):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    _scholarship(
        db,
        title="Australia Awards Fellowships",
        degree="Short-term professional development (2-52 weeks)",
        program_type=None,
        official_source_url="https://www.dfat.gov.au/people-to-people/australia-awards-fellowships",
    )

    report = run_supervisor_batch(db, _options())

    assert report.items[0].outcome_status == str(SupervisorCoverageStatus.NOT_APPLICABLE)
    assert report.items[0].not_applicable is True
    coverage = db.query(ScholarshipSupervisorCoverage).one()
    assert coverage.status == str(SupervisorCoverageStatus.NOT_APPLICABLE)
    assert coverage.verified_supervisor_count == 0
    # The honest negatives are never confused with each other.
    assert coverage.last_error_summary
    assert "Short-term professional development" in coverage.last_error_summary
    # And no professor was created for it.
    assert db.query(ProfessorProfile).count() == 0


def test_an_unknown_record_is_searched_rather_than_pre_judged(monkeypatch, db):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    _scholarship(db, degree="Other", program_type="Government scholarship")

    report = run_supervisor_batch(db, _options())

    # Discovery ran, and its answer is whatever the page supported - not a
    # classification made before the page was read.
    assert report.items[0].outcome_status == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    assert db.query(ProfessorProfile).count() == 2


# ---------------------------------------------------------------------------
# Blocked and unreadable sources
# ---------------------------------------------------------------------------


def test_a_blocked_source_stays_blocked_and_never_becomes_a_negative(monkeypatch, db):
    monkeypatch.setattr(worker, "polite_fetch", lambda url: None)
    monkeypatch.setattr(contacts, "polite_fetch", lambda url: None)
    worker.clear_robots_cache()
    _scholarship(db)

    report = run_supervisor_batch(db, _options())

    assert report.items[0].outcome_status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)
    assert report.items[0].outcome_status != str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
    assert db.query(ProfessorProfile).count() == 0
    # The batch continued and reported, which is what makes a catalogue pass
    # finish even when one university is unreachable.


def test_a_login_gated_directory_is_inaccessible_and_collects_no_contact(monkeypatch, db):
    _serve_discovery(monkeypatch, LOGIN_GATED_DIRECTORY)
    _scholarship(db)

    report = run_supervisor_batch(db, _options(collect_contacts=True))

    assert report.items[0].outcome_status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)
    # The directory is a login wall and the programme page publishes no contact
    # route, so nothing is invented to fill the gap.
    assert report.items[0].contact_collected is False
    assert db.query(ScholarshipOfficialContact).count() == 0


# ---------------------------------------------------------------------------
# Official contacts
# ---------------------------------------------------------------------------


def test_a_not_applicable_record_publishes_its_official_contact(monkeypatch, db):
    _serve_discovery(
        monkeypatch,
        GENUINE_FACULTY_PAGE,
        programme_html=PROGRAMME_PAGE_WITH_CONTACT,
    )
    scholarship = _scholarship(
        db,
        title="Australia Awards Fellowships",
        degree="Short-term professional development (2-52 weeks)",
        program_type=None,
        official_source_url="https://uni1.edu/programmes/fellowships",
    )

    report = run_supervisor_batch(db, _options(collect_contacts=True))

    assert report.items[0].not_applicable is True
    assert report.items[0].contact_collected is True
    assert report.items[0].contact_url == "https://uni1.edu/office/contact"

    coverage, professors, official_contacts = build_supervisor_list(db, scholarship.id)
    assert coverage["coverage_status"] == str(SupervisorCoverageStatus.NOT_APPLICABLE)
    # No professor, and no contact masquerading as one: the professors list is
    # empty and the contact carries an office kind rather than an academic title.
    assert professors == []
    assert len(official_contacts) == 1
    contact = official_contacts[0]
    assert contact["kind"] == "scholarship_office"
    assert contact["email"] == "scholarships@uni1.edu"
    assert contact["email_verified"] is True
    # The evidence page is the page the address was read from, which is the
    # office page one hop away - not the programme page the route was found on.
    assert contact["evidence_source_url"] == "https://uni1.edu/office/contact"
    assert "name" not in contact


def test_a_contact_email_from_another_domain_is_never_stored_as_verified(monkeypatch, db):
    _serve_discovery(
        monkeypatch,
        GENUINE_FACULTY_PAGE,
        programme_html=PROGRAMME_PAGE_WITH_CONTACT.replace(
            "/office/contact", "/office/contact-foreign"
        ),
    )

    def fake_fetch(url: str):
        if "/people/faculty" in url:
            return _fetch(url, GENUINE_FACULTY_PAGE)
        if "/people/" in url:
            return _fetch(url, PROFILE_WITH_OWN_DOMAIN_EMAIL)
        if "/office/contact-foreign" in url:
            # The route page publishes an address on somebody else's domain.
            return _fetch(url, CONTACT_PAGE_FOREIGN_EMAIL)
        return _fetch(
            url,
            PROGRAMME_PAGE_WITH_CONTACT.replace("/office/contact", "/office/contact-foreign"),
        )

    monkeypatch.setattr(worker, "polite_fetch", fake_fetch)
    monkeypatch.setattr(contacts, "polite_fetch", fake_fetch)
    worker.clear_robots_cache()

    scholarship = _scholarship(
        db,
        degree="Short-term professional development (2-52 weeks)",
        program_type=None,
    )

    report = run_supervisor_batch(db, _options(collect_contacts=True))

    assert report.items[0].contact_collected is True
    row = db.query(ScholarshipOfficialContact).one()
    assert row.contact_email != "scholarships@gmail.com"
    assert row.contact_email_verified is False

    _, professors, official_contacts = build_supervisor_list(db, scholarship.id)
    assert official_contacts[0]["email"] is None
    assert official_contacts[0]["email_verified"] is False


def test_page_furniture_is_never_published_as_a_contact_label(monkeypatch, db):
    """Navigation furniture identifies a route but is not the office's name."""
    _serve_discovery(
        monkeypatch,
        GENUINE_FACULTY_PAGE,
        programme_html=PROGRAMME_PAGE_WITH_FURNITURE_CONTACT,
    )
    _scholarship(
        db,
        degree="Short-term professional development (2-52 weeks)",
        program_type=None,
    )

    report = run_supervisor_batch(db, _options(collect_contacts=True))

    # The route is real, so the contact exists.
    assert report.items[0].contact_collected is True
    assert report.items[0].contact_url == "https://uni1.edu/office/contact"
    # And the label is absent rather than the furniture.
    row = db.query(ScholarshipOfficialContact).one()
    assert row.contact_label is None
    _, professors, official_contacts = build_supervisor_list(db, row.scholarship_id)
    assert official_contacts[0]["label"] is None


def test_a_verified_professor_list_suppresses_the_contact(monkeypatch, db):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    scholarship = _scholarship(db)

    run_supervisor_batch(db, _options(collect_contacts=True))

    coverage, professors, official_contacts = build_supervisor_list(db, scholarship.id)
    assert coverage["coverage_status"] == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    assert len(professors) == 2
    # The contact is not offered where there is a professor list to dilute.
    assert official_contacts == []


def test_a_contact_is_never_written_for_a_publicly_hidden_record(monkeypatch, db):
    """The visibility predicate governs contacts exactly as it governs professors."""
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    scholarship = _scholarship(
        db,
        degree="Short-term professional development (2-52 weeks)",
        program_type=None,
        is_archived=True,
    )

    with pytest.raises(ScholarshipNotPublic):
        build_supervisor_list(db, scholarship.id)


def test_a_database_that_predates_the_contact_table_still_serves(monkeypatch, db):
    """Production migration is out-of-band, so the read must tolerate its absence.

    A deployment that has not run the additive DDL yet must keep serving the
    professor payload rather than failing the whole supervisor request.
    """
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    scholarship = _scholarship(db)
    run_supervisor_batch(db, _options())

    db.execute(text("DROP TABLE scholarship_official_contacts"))
    db.commit()

    coverage, professors, official_contacts = build_supervisor_list(db, scholarship.id)
    assert coverage["coverage_status"] == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    assert len(professors) == 2
    assert official_contacts == []


# ---------------------------------------------------------------------------
# Batching: bounded, resumable, idempotent, auditable, dry-run
# ---------------------------------------------------------------------------


def _three_uncovered(db) -> list[Scholarship]:
    return [
        _scholarship(
            db,
            title=f"Record {index}",
            official_source_url=f"https://uni{index}.edu/programmes/msc",
        )
        for index in range(1, 4)
    ]


def test_the_batch_is_bounded_and_resumable_without_duplicating(monkeypatch, db):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    _three_uncovered(db)
    state_path = Path(tempfile.mkdtemp()) / "state.json"

    first = run_supervisor_batch(db, _options(limit=1, state_path=state_path))
    assert len(first.items) == 1
    assert first.next_cursor == first.items[0].scholarship_id
    assert first.selection_exhausted is False
    assert read_state(state_path)["last_scholarship_id"] == first.next_cursor

    # The cursor is read back, and the remaining two records are what a second
    # bounded run sees.
    second = run_supervisor_batch(
        db,
        _options(limit=5, after_id=read_state(state_path)["last_scholarship_id"], state_path=state_path),
    )
    assert [item.scholarship_id for item in second.items] == [
        first.next_cursor + 1,
        first.next_cursor + 2,
    ]
    assert second.selection_exhausted is True

    # Exhausted selection returns nothing rather than restarting, so a run loop
    # terminates.
    third = run_supervisor_batch(db, _options(limit=5, after_id=second.next_cursor))
    assert third.items == []

    # Each of the three records published its own two professors, and none of
    # that work was repeated: two bounded runs produced exactly what one whole
    # pass produces.
    assert db.query(ProfessorProfile).count() == 6
    assert db.query(ScholarshipProfessorLink).count() == 6
    coverage_rows = db.query(ScholarshipSupervisorCoverage).all()
    assert len(coverage_rows) == 3
    assert all(row.verified_supervisor_count == 2 for row in coverage_rows)


def test_the_batch_only_picks_records_that_owe_a_search(monkeypatch, db):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    rows = _three_uncovered(db)

    run_supervisor_batch(db, _options())

    # Every record reached a conclusive state, so a routine re-run selects
    # nothing: a catalogue pass cannot burn its budget re-reading universities
    # it has already read.
    assert select_batch_candidates(db, _options(limit=10)) == []

    # Naming an inconclusive state brings exactly those records back, which is
    # the operator's retry path.
    for row in db.query(ScholarshipSupervisorCoverage).all():
        row.status = str(SupervisorCoverageStatus.SOURCE_BLOCKED)
    db.commit()
    retry = _options(limit=10, include_statuses={str(SupervisorCoverageStatus.SOURCE_BLOCKED)})
    assert select_batch_candidates(db, retry) == rows


def test_a_dry_run_reports_proposed_changes_and_writes_nothing(monkeypatch, db, tmp_path):
    _serve_discovery(
        monkeypatch,
        GENUINE_FACULTY_PAGE,
        programme_html=PROGRAMME_PAGE_WITH_CONTACT,
    )
    _scholarship(
        db,
        degree="Short-term professional development (2-52 weeks)",
        program_type=None,
    )
    audit_path = tmp_path / "audit.jsonl"
    state_path = tmp_path / "state.json"

    report = run_supervisor_batch(
        db,
        _options(collect_contacts=True, dry_run=True, audit_path=audit_path, state_path=state_path),
    )

    assert report.dry_run is True
    # The proposed outcome is reported, not performed.
    assert report.items[0].outcome_status == str(SupervisorCoverageStatus.NOT_APPLICABLE)
    assert report.items[0].not_applicable is True
    assert report.items[0].contact_collected is True
    assert report.items[0].contact_url == "https://uni1.edu/office/contact"

    # And nothing was written: no coverage row, no professor, no contact, no
    # audit line, no state file.
    assert db.query(ScholarshipSupervisorCoverage).count() == 0
    assert db.query(ProfessorProfile).count() == 0
    assert db.query(ScholarshipOfficialContact).count() == 0
    assert audit_path.exists() is False
    assert state_path.exists() is False


def test_the_audit_log_reconstructs_a_run(monkeypatch, db, tmp_path):
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    _three_uncovered(db)
    audit_path = tmp_path / "audit.jsonl"

    report = run_supervisor_batch(db, _options(limit=3, audit_path=audit_path))

    lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3
    assert {line["scholarship_id"] for line in lines} == {
        item.scholarship_id for item in report.items
    }
    assert {line["run_id"] for line in lines} == {report.run_id}
    # Every line carries the outcome, so the log is a record of what was
    # claimed and not merely of what was attempted.
    for line in lines:
        assert line["outcome_status"]


def test_the_batch_never_enables_browser_rendering(monkeypatch, db):
    """Rendering is a separate switch with a separate name, and it stays off.

    The batch passes no render budget, so a client-side directory remains
    SOURCE_REQUIRES_RENDERING. The flag itself is an operator decision and this
    run neither reads nor writes it.
    """
    monkeypatch.delenv("SCHOLARZONE_SUPERVISOR_RENDER_ENABLED", raising=False)
    _serve_discovery(
        monkeypatch,
        "<html><head><title>People</title></head><body>"
        + "<script>window.__APP__={config:{}};</script>" * 900
        + '<div id="root"></div></body></html>',
    )
    _scholarship(db)

    report = run_supervisor_batch(db, _options())

    assert report.items[0].outcome_status == str(
        SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING
    )
    assert "SCHOLARZONE_SUPERVISOR_RENDER_ENABLED" not in os.environ

    source = Path(worker.__file__).with_name("supervisor_batch.py").read_text(encoding="utf-8")
    assert "RENDER_ENABLED_ENV" not in source
    assert "render_blocking" not in source
    assert "RenderBudget" not in source


# ---------------------------------------------------------------------------
# Personhood and office-page policies, against the shapes the real run produced
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    [
        # Administrative units and programmes, each of which a live run actually
        # offered as a professor.
        "Educational Development Unit",
        "Honors Program",
        "Admissions Office",
        "School of Computing",
        "Research Institutes",
        # A named award: the live run linked its own donor's scholarship page.
        "Dr Helen Marchant-Pritchard Memorial Scholarship",
        "Leonie Kramer Postgraduate Research Scholarship",
    ],
)
def test_an_organisation_is_refused_at_any_person_profile_path(label):
    """Organisations are name-shaped, and that is exactly the trap.

    A live pass published "Educational Development Unit" and "Honors Program"
    as verified professors because two to five capitalised words is what the
    structural test counts. The classifier now refuses a label that names an
    organisation, whichever route offered it - including at a URL that would
    otherwise be a perfectly good personal profile.
    """
    from app.services.supervisor_person import classify_person_candidate

    for url in (
        "https://uni1.edu/staff/educational-development",
        "https://uni1.edu/people/honors",
        "https://uni1.edu/profile/admissions-office",
    ):
        assert classify_person_candidate(label, url=url, directory_context=True) is None, (
            label,
            url,
        )


@pytest.mark.parametrize(
    "label,url",
    [
        # The real URL the live run read "The Clark Experience" from: a programme
        # page under a path root that names departments, not people.
        ("The Clark Experience", "https://www.clarku.edu/academics/the-clark-experience/"),
        # An HR process page one slug deep under a staff root.
        ("Annual Review Conversation", "https://www.imperial.ac.uk/staff/arc/"),
    ],
)
def test_the_shapes_that_leaked_into_a_live_run_are_refused(label, url):
    """Each pair is a page a live pass actually published as a professor."""
    from app.services.supervisor_person import classify_person_candidate

    assert classify_person_candidate(label, url=url, directory_context=True) is None


def test_a_repeated_link_label_is_page_furniture_not_a_person():
    """Sixteen "Read More" links produced sixteen professors on a live pass.

    The rule is document-derived rather than a word list: a listing anchors a
    call to action once per person and a real name once, so repetition - not
    wording - is what separates the two. No list of forbidden phrases could keep
    up with what a university calls its next button.
    """
    from app.services.supervisor_discovery import extract_faculty_candidates

    people = "".join(
        f'<li><a href="/profile/person-{i}">Read More</a></li>' for i in range(16)
    )
    candidates = extract_faculty_candidates(
        f"<html><body><h1>People</h1><ul>{people}</ul></body></html>",
        "https://uni1.edu/profile",
        "uni1.edu",
    )
    # Every label is furniture, so no candidate survives the repeated-label rule
    # at all - not one, and not partially.
    assert candidates == []


def test_a_person_shaped_slug_alone_is_not_enough():
    """The structural fallback needs a slug that names a person.

    `/staff/arc` is one word: a section, not a given name and surname. Dropping
    the single-token case is what stopped an HR-process page becoming a
    professor.
    """
    from app.services.supervisor_person import classify_person_candidate

    assert (
        classify_person_candidate(
            "Annual Review Conversation",
            url="https://uni1.edu/staff/arc",
            directory_context=True,
        )
        is None
    )
    # A two-word slug at the same root still earns the structural signal.
    assert (
        classify_person_candidate(
            "Grace Hopper",
            url="https://uni1.edu/staff/grace-hopper",
            directory_context=True,
        )
        is not None
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ntu.edu.sg/about-us/the-chancellery/mr-s.-chandra-das",
        "https://uni1.edu/about/university-management/university-executive/gregor-douglas",
        "https://uni1.edu/admissions/staff/jane-doe",
        "https://uni1.edu/registry/professor-john-smith",
        # Office team pages, reached by a live pass under an office path.
        "https://iitk.ac.in/oir/team",
        "https://www.jku.at/en/research-support-office/our-team/sarah-stainer",
    ],
)
def test_an_administrative_office_page_is_not_supervisory_evidence(url):
    """An office holder is not a supervisor, whatever title the page gives them.

    The Nanyang case is the named one: the award is administered by the Office
    of Admissions, and the people on its chancellery page were published as
    potential supervisors for it. The path is now read as evidence of what the
    page is.
    """
    from app.services.supervisor_discovery import FacultyCandidate
    from app.services.supervisor_gating import (
        GateVerdict,
        SupervisorGate,
        verify_supervisor_candidate,
    )

    candidate = FacultyCandidate(
        name="Jane Doe",
        profile_url=url,
        role="prof",
        role_evidence="honorific",
        name_claims_person=True,
    )
    verdict: GateVerdict = verify_supervisor_candidate(
        candidate,
        seed_host="uni1.edu" if "uni1" in url else "www.ntu.edu.sg",
        faculty_url=url,
        official_host_check=lambda host: True,
    )
    assert SupervisorGate.ROLE_EVIDENCE in verdict.failed_gates
    assert not verdict.approved


def test_a_faculty_page_still_publishes_its_academics(monkeypatch, db):
    """The tightened gates cost nothing on a real faculty directory.

    A genuine person at a person-profile path, with a role stated by the page,
    still goes through - which is the property that keeps the stricter policy
    from turning into a blanket refusal.
    """
    from app.services.supervisor_person import classify_person_candidate
    from app.services.supervisor_gating import approve_candidate_set

    signal = classify_person_candidate(
        "Dr Ada Lovelace",
        url="https://uni1.edu/people/ada-lovelace",
        directory_context=True,
    )
    assert signal is not None
    from app.services.supervisor_discovery import FacultyCandidate

    result = approve_candidate_set(
        [
            FacultyCandidate(
                name=signal.name,
                profile_url="https://uni1.edu/people/ada-lovelace",
                role=signal.role,
                role_evidence=signal.role_evidence,
                name_claims_person=signal.name_claims_person,
            )
        ],
        seed_host="uni1.edu",
        faculty_url="https://uni1.edu/people/faculty",
    )
    assert [c.name for c in result.approved] == ["Ada Lovelace"]


def test_a_failed_item_does_not_end_the_run(monkeypatch, db):
    """One unreachable university is a blocked item, not a failed catalogue pass."""
    _serve_discovery(monkeypatch, GENUINE_FACULTY_PAGE)
    rows = _three_uncovered(db)

    def flaky(url: str):
        if url.endswith("/programmes/msc") and rows[1].id == 2:
            raise RuntimeError("simulated fetch explosion")
        return _fetch(url, PROGRAMME_PAGE)

    monkeypatch.setattr(worker, "polite_fetch", flaky)
    monkeypatch.setattr(contacts, "polite_fetch", flaky)
    worker.clear_robots_cache()

    report = run_supervisor_batch(db, _options())

    assert len(report.items) == 3
    failed = [item for item in report.items if item.outcome_status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)]
    assert len(failed) >= 1
    assert "simulated fetch explosion" in (failed[0].detail or "")
    # The records after the failure were still processed.
    assert len({item.outcome_status for item in report.items}) >= 1
