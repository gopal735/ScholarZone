"""Supervisor Discovery on current master: the public surface and the data model.

Exercised against real ORM rows on an isolated in-memory database, because most
of what matters here is relational: a unique constraint that actually refuses a
duplicate, a coverage row that actually covers every scholarship, and a public
response that actually withholds a professor whose evidence is missing.

Identity comes from master's own auth (`/auth/register`, cookie
``scholarzone_session``, resolved by ``app.dependencies.require_user``). This
suite creates no identity system of its own and imports no auth helper beyond
registering a real account.

The visibility gates are pinned for the duration of each module and restored
afterwards. They live in a cached settings object, so a test that left them
changed would decide the outcome of whichever module ran next.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date, datetime, timedelta, timezone  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.core import config as config_module  # noqa: E402
from app.core.rate_limit import supervisor_read_limiter  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Scholarship, User  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorAvailability,
    ProfessorOutreachRecord,
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
)
from app.services.supervisor_alignment import align_research  # noqa: E402
from app.services.supervisor_coverage import (  # noqa: E402
    backfill_coverage,
    coverage_invariant_report,
    ensure_coverage_row,
    recompute_coverage,
    supervisor_universe_report,
)
from app.services.supervisor_freshness import (  # noqa: E402
    CONTACT_REFRESH_DAYS,
    effective_availability_state,
)
from app.services.supervisor_status import (  # noqa: E402
    AvailabilityState,
    ProfessorRelationshipType,
    RelationshipVerificationStatus,
    SupervisorCoverageStatus,
)

GATE_VARS = (
    "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED",
    "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE",
    "SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE",
)


def _reset_settings_cache() -> None:
    for attr in ("get_settings", "_get_settings"):
        candidate = getattr(config_module, attr, None)
        clear = getattr(candidate, "cache_clear", None)
        if callable(clear):
            clear()


@pytest.fixture
def pin_gates():
    previous = {name: os.environ.get(name) for name in GATE_VARS}
    for name in GATE_VARS:
        os.environ[name] = "false"
    _reset_settings_cache()
    yield
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    _reset_settings_cache()


def _record(index: int, **overrides) -> dict:
    base = {
        "title": f"Test Scholarship {index}",
        "country": "Germany",
        "degree": "Master",
        "funding": "Fully Funded",
        "status": "open",
        "deadline_date": date(2027, 6, 30),
        "deadline_precision": "exact",
        "eligibility": [],
        "coverage": [],
        "requirements": [],
        "documents": [],
        "official_source": f"Test University {index}",
        "official_source_url": f"https://uni{index}.edu/programmes/{index}",
        "is_verified": True,
        "verification_status": "active",
        "image_url": f"https://uni{index}.edu/logo.png",
    }
    base.update(overrides)
    return base


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


@pytest.fixture
def client(pin_gates, db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    supervisor_read_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _seed_public_scholarship(session, **overrides) -> Scholarship:
    row = Scholarship(**_record(1, **overrides))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _seed_professor(
    session,
    *,
    name: str = "Dr Ada Lovelace",
    url: str = "https://uni1.edu/people/ada-lovelace",
    email: str | None = "a.lovelace@uni1.edu",
    email_verified: bool = True,
    areas: list[str] | None = None,
    institution: str = "Test University 1",
) -> ProfessorProfile:
    profile = ProfessorProfile(
        canonical_name=name,
        title="Professor",
        institution_name=institution,
        department_name="Computer Science",
        official_profile_url=url,
        official_email=email,
        official_email_verified=email_verified,
        research_areas=areas if areas is not None else ["Machine Learning", "Computer Vision"],
        last_verified_at=datetime.now(timezone.utc),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def _seed_link(
    session,
    scholarship: Scholarship,
    professor: ProfessorProfile,
    *,
    status: str = str(RelationshipVerificationStatus.VERIFIED),
    relationship: str = str(ProfessorRelationshipType.POTENTIAL_SUPERVISOR),
    source_url: str = "https://uni1.edu/people/faculty",
    source_type: str = "official_department_page",
) -> ScholarshipProfessorLink:
    link = ScholarshipProfessorLink(
        scholarship_id=scholarship.id,
        professor_id=professor.id,
        relationship_type=relationship,
        evidence_source_url=source_url,
        evidence_source_type=source_type,
        evidence_quote_or_summary="Listed on the faculty page.",
        retrieved_at=datetime.now(timezone.utc),
        verified_at=(
            datetime.now(timezone.utc) if status == str(RelationshipVerificationStatus.VERIFIED) else None
        ),
        verification_status=status,
        confidence=80,
    )
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_every_scholarship_receives_exactly_one_coverage_row(db):
    for index in range(1, 6):
        db.add(Scholarship(**_record(index)))
    db.commit()

    result = backfill_coverage(db)

    assert result.created == 5
    rows = db.query(ScholarshipSupervisorCoverage).all()
    assert len(rows) == 5
    assert len({row.scholarship_id for row in rows}) == 5
    # A fresh row asserts nothing. Defaulting to zero supervisors would be a
    # claim; defaulting to search_pending is an admission of ignorance.
    assert all(row.status == str(SupervisorCoverageStatus.SEARCH_PENDING) for row in rows)
    assert all(row.verified_supervisor_count == 0 for row in rows)


def test_coverage_backfill_is_idempotent(db):
    for index in range(1, 4):
        db.add(Scholarship(**_record(index)))
    db.commit()

    first = backfill_coverage(db)
    second = backfill_coverage(db)
    third = backfill_coverage(db)

    assert first.created == 3
    # A repeat run finds nothing left to cover and writes nothing. It does not
    # re-read the already-covered rows either, which is what lets a backfill
    # progress past its first batch instead of looping on it.
    assert second.created == 0 and second.scanned == 0
    assert third.created == 0 and third.scanned == 0
    assert db.query(ScholarshipSupervisorCoverage).count() == 3


def test_coverage_backfill_advances_past_its_first_batch(db):
    # The regression this guards: selecting the lowest ids unconditionally makes a
    # backfill look stuck on batch one forever.
    for index in range(1, 8):
        db.add(Scholarship(**_record(index)))
    db.commit()

    first = backfill_coverage(db, batch_size=3)
    second = backfill_coverage(db, batch_size=3)

    assert first.created == 3
    assert second.created == 3
    assert db.query(ScholarshipSupervisorCoverage).count() == 6


def test_coverage_invariant_report_passes_when_every_row_is_present(db):
    for index in range(1, 4):
        db.add(Scholarship(**_record(index)))
    db.commit()
    backfill_coverage(db)

    report = coverage_invariant_report(db)

    assert report["invariant_holds"] is True
    assert report["missing_coverage_ids"] == []
    assert report["count_drift_ids"] == []
    assert report["total_scholarships"] == report["coverage_rows"] == 3


def test_coverage_invariant_report_names_a_scholarship_missing_a_row(db):
    db.add(Scholarship(**_record(1)))
    db.add(Scholarship(**_record(2)))
    db.commit()
    backfill_coverage(db, batch_size=1)

    report = coverage_invariant_report(db)

    assert report["invariant_holds"] is False
    assert len(report["missing_coverage_ids"]) == 1


def test_zero_supervisors_is_a_valid_state_not_a_failure(db):
    scholarship = _seed_public_scholarship(db)

    coverage = recompute_coverage(db, scholarship.id, searched=True)

    assert coverage.status == str(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
    assert coverage.verified_supervisor_count == 0


def test_an_unreached_search_never_becomes_a_negative_result(db):
    scholarship = _seed_public_scholarship(db)

    coverage = recompute_coverage(db, scholarship.id, searched=False, blocked=False)

    assert coverage.status == str(SupervisorCoverageStatus.SEARCH_PENDING)
    assert coverage.verified_supervisor_count == 0


def test_a_blocked_source_is_not_downgraded_to_pending(db):
    scholarship = _seed_public_scholarship(db)

    coverage = recompute_coverage(db, scholarship.id, searched=False, blocked=True)

    assert coverage.status == str(SupervisorCoverageStatus.SOURCE_BLOCKED)


def test_coverage_count_tracks_the_links_behind_it(db):
    scholarship = _seed_public_scholarship(db)
    first = _seed_professor(db, name="Dr Grace Hopper", url="https://uni1.edu/people/grace-hopper")
    second = _seed_professor(db, name="Dr Alan Turing", url="https://uni1.edu/people/alan-turing")
    _seed_link(db, scholarship, first)
    _seed_link(db, scholarship, second)

    recompute_coverage(db, scholarship.id, searched=True)
    recompute_coverage(db, scholarship.id, searched=True)

    coverage = db.query(ScholarshipSupervisorCoverage).one()
    assert coverage.status == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    assert coverage.verified_supervisor_count == 2


# ---------------------------------------------------------------------------
# Phase 3: production universe contract
# ---------------------------------------------------------------------------


def test_universe_report_uses_the_catalogue_predicate(db):
    for index in range(1, 4):
        db.add(Scholarship(**_record(index)))
    db.commit()
    backfill_coverage(db)

    report = supervisor_universe_report(db)

    # The universe is the catalogue Count Intelligence already defines, not
    # "every row in the table". Restating it here would be a second answer to
    # "what population is this count about".
    assert report["universe"] == "CATALOGUE"
    assert report["universe_predicate_source"] == (
        "app.repositories.scholarships.public_visibility_conditions"
    )
    assert report["universe_size"] == 3
    assert report["covered_in_universe"] == 3
    assert report["invariant_holds"] is True


def test_archived_records_are_outside_the_universe_but_may_hold_coverage(db):
    public = _seed_public_scholarship(db)
    archived = _seed_public_scholarship(
        db, official_source_url="https://uni1.edu/p2", is_archived=True
    )
    backfill_coverage(db)

    report = supervisor_universe_report(db)

    assert report["universe_size"] == 1
    assert archived.id in report["coverage_rows_outside_universe"]


def test_quarantined_records_are_outside_the_universe(db):
    _seed_public_scholarship(db, verification_status="quarantined")
    backfill_coverage(db)

    report = supervisor_universe_report(db)

    assert report["universe_size"] == 0
    assert report["invariant_holds"] is True
    assert report["coverage_rows_total"] == 1


def test_universe_invariant_fails_when_a_visible_scholarship_has_no_coverage(db):
    _seed_public_scholarship(db)
    backfill_coverage(db, batch_size=1)
    # Remove the row directly to simulate a partial backfill.
    db.query(ScholarshipSupervisorCoverage).delete()
    db.commit()

    report = supervisor_universe_report(db)

    assert report["invariant_holds"] is False
    assert len(report["uncovered_in_universe"]) == 1


# ---------------------------------------------------------------------------
# Duplicate prevention
# ---------------------------------------------------------------------------


def test_duplicate_professor_is_refused_by_the_database(db):
    _seed_professor(db)

    with pytest.raises(IntegrityError):
        _seed_professor(db, name="A Different Name", url="https://uni1.edu/people/ada-lovelace")
    db.rollback()


def test_duplicate_relationship_is_refused(db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)

    with pytest.raises(IntegrityError):
        _seed_link(db, scholarship, professor)
    db.rollback()


def test_same_professor_may_relate_to_two_scholarships(db):
    first = _seed_public_scholarship(db)
    second = _seed_public_scholarship(db, official_source_url="https://uni1.edu/programmes/2")
    professor = _seed_professor(db)

    _seed_link(db, first, professor)
    _seed_link(db, second, professor)

    assert db.query(ScholarshipProfessorLink).count() == 2
    assert db.query(ProfessorProfile).count() == 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def test_public_list_returns_verified_professors_with_provenance(client, db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(db)
    link = _seed_link(db, scholarship, professor)
    db.add(
        SupervisorSourceEvidence(
            professor_id=professor.id,
            scholarship_id=scholarship.id,
            link_id=link.id,
            source_url="https://uni1.edu/people/faculty",
            source_host="uni1.edu",
            source_type="official_department_page",
            retrieved_at=datetime.now(timezone.utc),
            verified_at=datetime.now(timezone.utc),
            verification_status=str(RelationshipVerificationStatus.VERIFIED),
            evidence_summary="Listed on the faculty page.",
        )
    )
    db.commit()

    response = client.get(f"/scholarships/{scholarship.id}/supervisors")

    assert response.status_code == 200
    payload = response.json()
    assert payload["coverage"]["coverage_status"] == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    assert payload["coverage"]["verified_supervisor_count"] == 1
    entry = payload["supervisors"][0]
    assert entry["name"] == "Dr Ada Lovelace"
    assert entry["official_email"] == "a.lovelace@uni1.edu"
    assert entry["official_email_verified"] is True
    assert entry["evidence_source_url"] == "https://uni1.edu/people/faculty"
    assert entry["sources"][0]["source_host"] == "uni1.edu"


def test_unverified_relationship_is_never_published(client, db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor, status=str(RelationshipVerificationStatus.UNVERIFIED))

    payload = client.get(f"/scholarships/{scholarship.id}/supervisors").json()

    assert payload["supervisors"] == []


def test_unverified_email_is_withheld_even_when_stored(client, db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(
        db, url="https://uni1.edu/people/no-email", email="guess@uni1.edu", email_verified=False
    )
    _seed_link(db, scholarship, professor)

    entry = client.get(f"/scholarships/{scholarship.id}/supervisors").json()["supervisors"][0]

    assert entry["official_email"] is None
    assert entry["official_email_verified"] is False


def test_response_never_exposes_private_or_internal_fields(client, db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)
    user = User(email="a@b.com", password_hash="x", is_active=True)
    db.add(user)
    db.commit()
    db.add(
        ProfessorOutreachRecord(
            user_id=user.id,
            scholarship_id=scholarship.id,
            professor_id=professor.id,
            status="sent",
            notes="a private note",
            draft_body="a private draft",
        )
    )
    db.commit()

    body = client.get(f"/scholarships/{scholarship.id}/supervisors").text

    for leaked in ("private note", "private draft", "user_id", "notes", "draft_body", "a@b.com"):
        assert leaked not in body


def test_summary_route_reports_state_without_professor_details(client, db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)
    recompute_coverage(db, scholarship.id, searched=True)

    payload = client.get(f"/scholarships/{scholarship.id}/supervisor-summary").json()

    assert payload["verified_supervisor_count"] == 1
    assert payload["coverage_status"] == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
    assert "supervisors" not in payload


def test_scholarship_with_no_coverage_row_reports_pending_not_zero_found(client, db):
    scholarship = _seed_public_scholarship(db)

    payload = client.get(f"/scholarships/{scholarship.id}/supervisors").json()

    assert payload["coverage"]["coverage_status"] == str(SupervisorCoverageStatus.SEARCH_PENDING)
    assert payload["coverage"]["discovery_pending"] is True
    assert payload["supervisors"] == []


def test_coverage_error_summary_is_never_public(client, db):
    scholarship = _seed_public_scholarship(db)
    coverage, _ = ensure_coverage_row(db, scholarship.id)
    coverage.last_error_summary = "403 from host faculty.uni1.edu internal-path /admin"
    db.commit()

    body = client.get(f"/scholarships/{scholarship.id}/supervisors").text

    assert "403" not in body
    assert "last_error_summary" not in body


# ---------------------------------------------------------------------------
# Phase 4: public visibility security
# ---------------------------------------------------------------------------


def test_archived_scholarship_exposes_no_supervisor_data(client, db):
    scholarship = _seed_public_scholarship(db, is_archived=True)
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)
    recompute_coverage(db, scholarship.id, searched=True)

    listed = client.get(f"/scholarships/{scholarship.id}/supervisors")
    summary = client.get(f"/scholarships/{scholarship.id}/supervisor-summary")

    assert listed.status_code == 404
    assert summary.status_code == 404
    # The coverage row still exists. Existing coverage must not make a hidden
    # record public - the row is an internal record, not a publication decision.
    assert db.query(ScholarshipSupervisorCoverage).count() == 1


def test_quarantined_scholarship_exposes_no_supervisor_data(client, db):
    scholarship = _seed_public_scholarship(db, verification_status="quarantined")
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)

    assert client.get(f"/scholarships/{scholarship.id}/supervisors").status_code == 404


def test_needs_review_scholarship_is_visible_and_may_carry_supervisors(client, db):
    # needs_review is not a visibility gate on master; it is a trust label. The
    # supervisor feature must follow the canonical predicate, not invent a
    # stricter one of its own.
    scholarship = _seed_public_scholarship(db, verification_status="needs_review")
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)

    response = client.get(f"/scholarships/{scholarship.id}/supervisors")

    assert response.status_code == 200
    assert len(response.json()["supervisors"]) == 1


def test_source_blocked_scholarship_is_not_exposed(client, db):
    scholarship = _seed_public_scholarship(db, is_archived=True)
    coverage, _ = ensure_coverage_row(db, scholarship.id)
    coverage.status = str(SupervisorCoverageStatus.SOURCE_BLOCKED)

    assert client.get(f"/scholarships/{scholarship.id}/supervisors").status_code == 404


def test_absent_scholarship_is_indistinguishable_from_hidden(client, db):
    archived = _seed_public_scholarship(db, is_archived=True)

    hidden = client.get(f"/scholarships/{archived.id}/supervisors")
    absent = client.get("/scholarships/999999/supervisors")

    assert hidden.status_code == absent.status_code == 404
    assert hidden.json() == absent.json()


def test_public_professor_data_requires_the_scholarships_own_visibility(client, db):
    # A professor who is public for one scholarship must not become readable
    # through a different, hidden scholarship that happens to link them.
    visible = _seed_public_scholarship(db)
    hidden = _seed_public_scholarship(
        db, official_source_url="https://uni2.edu/p", is_archived=True
    )
    professor = _seed_professor(db)
    _seed_link(db, visible, professor)
    _seed_link(db, hidden, professor)

    assert len(client.get(f"/scholarships/{visible.id}/supervisors").json()["supervisors"]) == 1
    assert client.get(f"/scholarships/{hidden.id}/supervisors").status_code == 404


# ---------------------------------------------------------------------------
# Availability and freshness
# ---------------------------------------------------------------------------


def test_availability_defaults_to_not_published_rather_than_a_guess(client, db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)
    db.add(
        ProfessorAvailability(
            professor_id=professor.id,
            scope="masters_supervision",
            state=str(AvailabilityState.NOT_PUBLISHED),
            source_url=professor.official_profile_url,
            verified_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    entry = client.get(f"/scholarships/{scholarship.id}/supervisors").json()["supervisors"][0]

    assert entry["availability"][0]["state"] == str(AvailabilityState.NOT_PUBLISHED)
    assert entry["availability"][0]["source_url"] == professor.official_profile_url


def test_availability_is_only_ever_reported_with_a_source_and_a_date(client, db):
    scholarship = _seed_public_scholarship(db)
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)
    db.add(
        ProfessorAvailability(
            professor_id=professor.id,
            scope="phd_supervision",
            state=str(AvailabilityState.VERIFIED_YES),
            source_url="https://uni1.edu/people/ada-lovelace",
            verified_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    claim = client.get(f"/scholarships/{scholarship.id}/supervisors").json()["supervisors"][0][
        "availability"
    ][0]

    assert claim["state"] == str(AvailabilityState.VERIFIED_YES)
    assert claim["source_url"].startswith("https://")
    assert claim["verified_at"] is not None


def test_a_stale_verified_claim_is_published_as_stale():
    old = datetime.now(timezone.utc) - timedelta(days=CONTACT_REFRESH_DAYS + 5)

    assert effective_availability_state(str(AvailabilityState.VERIFIED_YES), old) == str(
        AvailabilityState.STALE
    )


def test_an_absence_never_decays_into_stale():
    old = datetime.now(timezone.utc) - timedelta(days=CONTACT_REFRESH_DAYS * 3)

    assert effective_availability_state(str(AvailabilityState.NOT_PUBLISHED), old) == str(
        AvailabilityState.NOT_PUBLISHED
    )
    assert effective_availability_state(str(AvailabilityState.UNKNOWN), old) == str(
        AvailabilityState.UNKNOWN
    )


# ---------------------------------------------------------------------------
# Research alignment
# ---------------------------------------------------------------------------


def test_no_interests_yields_insufficient_evidence():
    result = align_research([], ["Machine Learning"])

    assert result.band == "insufficient_evidence"
    assert "No research interests" in result.explanation


def test_phrase_overlap_is_strong():
    result = align_research(["machine-learning"], ["Machine Learning", "Computer Vision"])

    assert result.band == "strong_research_alignment"


def test_disjoint_interests_are_insufficient_not_a_weak_match():
    result = align_research(["Marine Biology"], ["Machine Learning"])

    assert result.band == "insufficient_evidence"
    assert "No overlap" in result.explanation


def test_alignment_never_produces_a_number():
    result = align_research(["Machine Learning"], ["Machine Learning"])

    for forbidden in ("%", "probability", "chance"):
        assert forbidden not in result.explanation.lower()


def test_generic_word_does_not_manufacture_moderate_alignment():
    # "approaches" alone is a coincidence, not an alignment.
    result = align_research(["research in new approaches"], ["New Approaches"])

    assert result.band != "moderate_research_alignment"


# ---------------------------------------------------------------------------
# Isolation from the systems that must not move
# ---------------------------------------------------------------------------


def test_catalogue_totals_are_unchanged_by_supervisor_data(client, db):
    for index in range(1, 4):
        db.add(Scholarship(**_record(index)))
    db.commit()
    before = client.get("/scholarships/stats").json()

    scholarship = db.query(Scholarship).first()
    professor = _seed_professor(db)
    _seed_link(db, scholarship, professor)
    recompute_coverage(db, scholarship.id, searched=True)

    after = client.get("/scholarships/stats").json()

    assert before["total"] == after["total"]
    assert before["verified_active"] == after["verified_active"]


def test_match_scoring_is_unchanged_by_supervisor_data(client, db):
    _seed_public_scholarship(db)
    payload = {
        "citizenship": "India",
        "intended_degree_level": "MASTER",
        "overall_result": {"scale": "GPA_4", "value": 3.9},
        "preferred_countries": ["Germany"],
        "funding_requirement": "FULL_FUNDING",
    }
    before = client.post("/scholarships/match", json=payload).json()

    scholarship = db.query(Scholarship).first()
    professor = _seed_professor(db, areas=["Machine Learning"])
    _seed_link(db, scholarship, professor)
    recompute_coverage(db, scholarship.id, searched=True)

    after = client.post("/scholarships/match", json=payload).json()

    # Alignment is a separate explanatory signal and must not leak into the fit
    # score or reorder the ranking.
    assert before["summary"] == after["summary"]
    assert [item.get("id") for item in before.get("results", [])] == [
        item.get("id") for item in after.get("results", [])
    ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_limit_outside_the_allowed_range_is_rejected(client, db):
    scholarship = _seed_public_scholarship(db)

    assert client.get(f"/scholarships/{scholarship.id}/supervisors?limit=0").status_code == 422
    assert client.get(f"/scholarships/{scholarship.id}/supervisors?limit=99999").status_code == 422


def test_reads_are_rate_limited(client, db):
    scholarship = _seed_public_scholarship(db)

    statuses = [
        client.get(f"/scholarships/{scholarship.id}/supervisor-summary").status_code
        for _ in range(200)
    ]

    assert 429 in statuses
    assert statuses[0] == 200