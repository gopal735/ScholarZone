"""The no-write boundary: nothing is stored until every gate has been applied.

This file exists because "we validate first, then write" is a claim about
ordering, and an ordering claim that is only kept in someone's head decays. Each
test below pins one specific way the claim could stop being true, and the last
class pins the *shape* of the code so the claim cannot be quietly undone by a
later edit.

The gates under test are the six in
:mod:`app.services.supervisor_gating`. What matters is not that a candidate is
refused, but that refusal happens with an empty database - because a candidate
that is created and then hidden is a claim the product is still making.

No test here touches a real university. Every page is a fixture string, and the
network guard is installed so a code path that escapes to the internet fails here
rather than on somebody else's outage.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
)
from app.services import supervisor_discovery as worker  # noqa: E402
from app.services.supervisor_discovery import (  # noqa: E402
    ApprovedCandidateGroup,
    collect_supervisor_plan,
    discover_for_scholarship,
    persist_supervisor_plan,
)
from app.services.supervisor_gating import (  # noqa: E402
    ApprovedSupervisorCandidate,
    SupervisorGate,
    approve_candidate_set,
    name_is_person_shaped,
    verification_status_for,
    verify_supervisor_candidate,
)

REPO_BACKEND = Path(__file__).resolve().parents[1]
DISCOVERY_SOURCE = REPO_BACKEND / "app" / "services" / "supervisor_discovery.py"
GATING_SOURCE = REPO_BACKEND / "app" / "services" / "supervisor_gating.py"

UNIVERSITY = "uni1.edu"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        "official_source_url": f"https://{UNIVERSITY}/programmes/msc",
        "is_verified": True,
        "verification_status": "active",
    }
    base.update(overrides)
    row = Scholarship(**base)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _fetch_result(url: str, content: str, status: int = 200):
    from app.services.official_source_fetcher import OfficialSourceFetchResult

    return OfficialSourceFetchResult(
        success=True,
        status_code=status,
        final_url=url,
        content=content,
        content_type="text/html",
    )


def _serve(monkeypatch, pages: dict[str, str]):
    """Serve ``pages`` and forbid every other network read."""

    def fake_polite_fetch(url: str):
        content = pages.get(url.split("#")[0])
        if content is None:
            return None
        return _fetch_result(url, content)

    monkeypatch.setattr(worker, "polite_fetch", fake_polite_fetch)
    worker.clear_robots_cache()
    return pages


PROGRAMME_PAGE = f"""
<html><body><h1>MSc Computer Science</h1>
  <a href="/people/faculty">Our Faculty</a>
</body></html>
"""

#: A directory whose every listed entry is *meant* to be refused. Each row fails a
#: different gate, and none of them should reach storage.
ALL_INVALID_DIRECTORY = f"""
<html><body><h1>Faculty</h1>
  <ul>
    <li><a href="/people/academic-staff">Academic Staff</a></li>
    <li><a href="/people/school-of-computing">School of Computing</a></li>
    <li><a href="/people/ada-lovelace">Ada Lovelace</a></li>
    <li><a href="/people/apply-now">Apply Now</a></li>
  </ul>
</body></html>
"""

#: One genuine professor with a stated role, for the positive-path tests.
VALID_DIRECTORY = f"""
<html><body><h1>Faculty</h1>
  <ul>
    <li><a href="/people/grace-hopper">Professor Grace Hopper</a></li>
    <li><a href="/people/ada-lovelace">Dr Ada Lovelace</a></li>
  </ul>
</body></html>
"""

VALID_PROFILE = """
<html><body><h1>Professor Grace Hopper</h1>
  <p>Professor of Computer Science</p>
  <p>Research interests: compilers</p>
</body></html>
"""

VALID_PROFILE_NO_ROLE = """
<html><body><h1>Ada Lovelace</h1>
  <p>Research interests: machine learning</p>
</body></html>
"""


#: The real Cornell Computer Science shape, reproduced exactly.
#:
#: Names are listed with **no** honorific and no role word, so the listing alone
#: proves personhood and nothing else. Role evidence can only come from the
#: profile page. One profile states a role; the other does not. This is the
#: distinction the production proof turns on, and it is why a person-shaped name
#: must never be reported as a verified professor on its own.
CORNELL_SHAPE_DIRECTORY = f"""
<html><body><h1>Faculty</h1>
  <ul>
    <li><a href="/people/grace-hopper">Grace Hopper</a></li>
    <li><a href="/people/ada-lovelace">Ada Lovelace</a></li>
  </ul>
</body></html>
"""


def _profile(body: str):
    """Serve one programme page and one directory page, nothing else.

    Every profile URL resolves to ``body``, so a test controls what role evidence
    the profile stage can possibly find by choosing the body.
    """
    return {
        f"https://{UNIVERSITY}/programmes/msc": PROGRAMME_PAGE,
        f"https://{UNIVERSITY}/people/faculty": VALID_DIRECTORY,
        f"https://{UNIVERSITY}/people/grace-hopper": VALID_PROFILE,
        f"https://{UNIVERSITY}/people/ada-lovelace": VALID_PROFILE_NO_ROLE,
    }


def _counts(db) -> dict[str, int]:
    return {
        "professors": db.execute(select(func.count(ProfessorProfile.id))).scalar_one(),
        "links": db.execute(select(func.count(ScholarshipProfessorLink.id))).scalar_one(),
        "coverage": db.execute(
            select(func.count(ScholarshipSupervisorCoverage.id))
        ).scalar_one(),
    }


def _names(db) -> list[str]:
    return sorted(
        db.execute(select(ProfessorProfile.canonical_name)).scalars().all()
    )


# ---------------------------------------------------------------------------
# A. Collection happens with zero database writes
# ---------------------------------------------------------------------------


class TestCollectionWritesNothing:
    def test_collecting_a_real_directory_writes_nothing(self, db, monkeypatch):
        """A. The whole pipeline can run to completion against an empty database."""
        scholarship = _scholarship(db)
        _serve(monkeypatch, _profile(VALID_PROFILE))

        plan = collect_supervisor_plan(scholarship)

        # The run really did find something; otherwise this proves nothing.
        assert plan.approved_count == 2, "the fixture must produce approvals"
        assert plan.pages_fetched > 0
        # ...and none of it has been stored.
        assert _counts(db) == {"professors": 0, "links": 0, "coverage": 0}

    def test_collection_needs_no_session_argument_at_all(self, db, monkeypatch):
        """A. The signature is the proof: there is nowhere to write from."""
        import inspect

        parameters = inspect.signature(collect_supervisor_plan).parameters
        assert "db" not in parameters
        assert "session" not in parameters
        assert parameters.keys() == {
            "scholarship",
            "render_budget",
            "official_host_check",
        }

    def test_the_gate_module_cannot_import_the_database_at_all(self):
        """A. The gate module is pure, so gating cannot depend on storage.

        Run in a subprocess with the database layer poisoned. If importing the
        gate module needs SQLAlchemy, the import raises and this test fails -
        which means the decision about whether a row exists cannot be made without
        the machinery that makes rows.
        """
        program = (
            "import sys\n"
            "class Poison:\n"
            "    def find_module(self, name, path=None):\n"
            "        return self if name.split('.')[0] == 'sqlalchemy' else None\n"
            "    def load_module(self, name):\n"
            "        raise ImportError('database layer is not importable here')\n"
            "sys.meta_path.insert(0, Poison())\n"
            "import app.services.supervisor_gating as gating\n"
            "assert 'sqlalchemy' not in sys.modules, 'the gate module pulled in SQLAlchemy'\n"
            "print('PURE')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=str(REPO_BACKEND),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "PURE" in result.stdout


# ---------------------------------------------------------------------------
# B/C/D. Each single gate, on its own, refuses and writes nothing
# ---------------------------------------------------------------------------


def _candidate(name, profile_url, role, role_evidence):
    from app.services.supervisor_discovery import FacultyCandidate

    return FacultyCandidate(
        name=name,
        profile_url=profile_url,
        role=role,
        role_evidence=role_evidence,
    )


class TestSingleGateRefusals:
    def test_b_role_restated_as_a_name_is_refused_by_the_personhood_gate(self):
        """B. "Academic Staff" states a role and names nobody.

        Judged at the gate rather than through the pipeline, because the
        classifier upstream refuses this text before a candidate is ever built -
        see the pipeline-level assertion below. The gate is the last line of
        defence, so it must refuse it independently.
        """
        verdict = verify_supervisor_candidate(
            _candidate(
                "Academic Staff",
                f"https://{UNIVERSITY}/people/academic-staff",
                "academic",
                "inline_role",
            ),
            seed_host=UNIVERSITY,
            faculty_url=f"https://{UNIVERSITY}/people/faculty",
        )
        assert not verdict.approved
        assert verdict.primary_failure == str(SupervisorGate.PERSONHOOD)

    def test_b_personhood_failure_produces_zero_persistence(self, db, monkeypatch):
        """B. Through the real pipeline: a directory of non-people stores nothing.

        The entries here are refused upstream by the classifier rather than by
        the gate, which is the better outcome, and the test asserts the property
        that matters either way - nothing was written - without pretending to know
        which layer did the refusing.
        """
        scholarship = _scholarship(db)
        pages = _profile(VALID_PROFILE)
        pages[f"https://{UNIVERSITY}/people/faculty"] = ALL_INVALID_DIRECTORY
        _serve(monkeypatch, pages)

        plan = collect_supervisor_plan(scholarship)
        assert plan.approved_count == 0
        persist_supervisor_plan(db, scholarship, plan)

        counts = _counts(db)
        assert counts["professors"] == 0
        assert counts["links"] == 0
        assert "Academic Staff" not in _names(db)
        assert "School of Computing" not in _names(db)

    def test_c_personhood_proven_but_role_not_proven_is_not_stored(self, db, monkeypatch):
        """C. The exact production-proof shape, and the claim it forbids.

        Both names are listed bare, so the listing establishes personhood and
        nothing else. Grace Hopper's profile states a role, so she is stored.
        Ada Lovelace's profile states none, so she is not - even though her name
        is exactly as person-shaped as Grace Hopper's.

        A production run must therefore be unable to report VERIFIED on the
        strength of personhood alone, and this is what makes that true of the code
        rather than of the prose.
        """
        scholarship = _scholarship(db)
        pages = _profile(VALID_PROFILE)
        pages[f"https://{UNIVERSITY}/people/faculty"] = CORNELL_SHAPE_DIRECTORY
        _serve(monkeypatch, pages)

        plan = collect_supervisor_plan(scholarship)
        assert plan.examined_count == 2, "both names must reach the gate"
        persist_supervisor_plan(db, scholarship, plan)

        assert _names(db) == ["Grace Hopper"]
        # Ada Lovelace reached the gate, was refused on role evidence, and the run
        # says so rather than quietly dropping her.
        assert plan.rejection_reasons.get(str(SupervisorGate.ROLE_EVIDENCE), 0) == 1
        assert plan.approved_count == 1

    def test_c_personhood_alone_never_yields_verified(self):
        """C. The personhood-versus-role distinction, stated as a unit test.

        This is the distinction the real-source proof depends on, and it is the
        one a future "simplification" is most likely to erase.
        """
        person_only = _candidate(
            "Grace Hopper", f"https://{UNIVERSITY}/people/grace-hopper", None, None
        )
        # The name is a perfectly good person-shaped name. What it lacks is a role.
        assert name_is_person_shaped(person_only.name) is True
        assert verification_status_for(person_only) == "unverified"

        with_role = _candidate(
            "Grace Hopper",
            f"https://{UNIVERSITY}/people/grace-hopper",
            "professor",
            "profile_role",
        )
        assert verification_status_for(with_role) == "verified"

    def test_d_off_institution_domain_produces_zero_persistence(self, db, monkeypatch):
        """D. Another university's directory is not evidence about this one."""
        scholarship = _scholarship(db)
        pages = {
            "https://uni1.edu/programmes/msc": """
                <html><body><a href="/people/faculty">Our Faculty</a></body></html>
            """,
            "https://uni1.edu/people/faculty": """
                <html><body><h1>Faculty</h1>
                  <a href="https://other-university.edu/people/grace-hopper">
                    Professor Grace Hopper</a>
                </body></html>
            """,
        }
        _serve(monkeypatch, pages)

        plan = collect_supervisor_plan(scholarship)
        persist_supervisor_plan(db, scholarship, plan)

        counts = _counts(db)
        assert counts["professors"] == 0
        assert counts["links"] == 0

    def test_d_off_domain_is_refused_by_the_gate_in_isolation(self):
        """D. The institutional-domain gate, without a database in the way.

        The pipeline screens cross-host links while collecting, so the gate rarely
        has to catch one; it is checked here on its own because it is the
        authority on the question and must hold without the upstream screen.
        """
        candidate = _candidate(
            "Grace Hopper",
            "https://elsewhere.edu/people/grace-hopper",
            "professor",
            "profile_role",
        )
        verdict = verify_supervisor_candidate(
            candidate,
            seed_host=UNIVERSITY,
            faculty_url=f"https://{UNIVERSITY}/people/faculty",
        )
        assert not verdict.approved
        assert SupervisorGate.INSTITUTIONAL_DOMAIN in verdict.failed_gates


# ---------------------------------------------------------------------------
# E/F. Mixed and wholly-invalid batches
# ---------------------------------------------------------------------------


class TestBatchComposition:
    def test_e_a_mixed_batch_persists_only_the_valid_candidates(self, db, monkeypatch):
        """E. Valid and invalid candidates in one run: only the valid are stored."""
        from app.services.supervisor_discovery import FacultyCandidate

        candidates = [
            # Valid: role stated, person-shaped, correct institution.
            FacultyCandidate(
                name="Grace Hopper",
                profile_url=f"https://{UNIVERSITY}/people/grace-hopper",
                role="professor",
                role_evidence="profile_role",
            ),
            # Invalid: role restated as a name.
            FacultyCandidate(
                name="Academic Staff",
                profile_url=f"https://{UNIVERSITY}/people/academic-staff",
                role="academic",
                role_evidence="inline_role",
            ),
            # Invalid: no role at all.
            FacultyCandidate(
                name="Ada Lovelace",
                profile_url=f"https://{UNIVERSITY}/people/ada-lovelace",
                role=None,
                role_evidence=None,
            ),
            # Invalid: another institution.
            FacultyCandidate(
                name="Katherine Johnson",
                profile_url="https://elsewhere.edu/people/katherine-johnson",
                role="professor",
                role_evidence="profile_role",
            ),
            # Invalid: a role claimed by a mechanism this product has not
            # reviewed. The value is not None, so a naive "did somebody claim a
            # role?" check would pass it.
            FacultyCandidate(
                name="Grace Kelly",
                profile_url=f"https://{UNIVERSITY}/people/grace-kelly",
                role="professor",
                role_evidence="guessed_from_a_footer",
            ),
        ]

        decision = approve_candidate_set(
            candidates,
            seed_host=UNIVERSITY,
            faculty_url=f"https://{UNIVERSITY}/people/faculty",
            seen_urls=set(),
        )

        assert len(decision.approved) == 1
        assert decision.approved[0].name == "Grace Hopper"
        assert decision.examined == 5
        assert decision.rejected == 4
        assert sum(decision.rejection_reasons.values()) == 4

    def test_e_a_mixed_run_persists_only_the_valid_candidates(self, db, monkeypatch):
        """E. The same claim, through the real pipeline and the real database."""
        scholarship = _scholarship(db)
        pages = _profile(VALID_PROFILE)
        pages[f"https://{UNIVERSITY}/people/faculty"] = """
            <html><body><h1>Faculty</h1><ul>
              <li><a href="/people/grace-hopper">Professor Grace Hopper</a></li>
              <li><a href="/people/academic-staff">Academic Staff</a></li>
              <li><a href="/people/apply-now">Apply Now</a></li>
              <li><a href="/people/ada-lovelace">Ada Lovelace</a></li>
            </ul></body></html>
        """
        _serve(monkeypatch, pages)

        plan = collect_supervisor_plan(scholarship)
        persist_supervisor_plan(db, scholarship, plan)

        assert _names(db) == ["Grace Hopper"]
        assert _counts(db)["links"] == 1
        # The run reported both sides of the ledger, not just the happy path.
        assert plan.approved_count == 1
        assert plan.rejected_count >= 2

    def test_f_a_wholly_invalid_run_creates_no_supervisor_rows(self, db, monkeypatch):
        """F. Every candidate fails: zero professors, zero relationships."""
        scholarship = _scholarship(db)
        pages = _profile(VALID_PROFILE)
        pages[f"https://{UNIVERSITY}/people/faculty"] = ALL_INVALID_DIRECTORY
        _serve(monkeypatch, pages)

        plan = collect_supervisor_plan(scholarship)
        assert plan.approved_count == 0
        persist_supervisor_plan(db, scholarship, plan)

        counts = _counts(db)
        assert counts["professors"] == 0
        assert counts["links"] == 0

    def test_f_a_wholly_invalid_run_still_records_what_it_learned(self, db, monkeypatch):
        """F. "We looked and found nothing" is itself an answer.

        The coverage row is written, at the single post-discovery boundary, and
        carries the honest negative. This is not a leak of a professor row: a
        coverage row records the state of a search, and the product requires every
        scholarship to have one.
        """
        scholarship = _scholarship(db)
        pages = _profile(VALID_PROFILE)
        pages[f"https://{UNIVERSITY}/people/faculty"] = ALL_INVALID_DIRECTORY
        _serve(monkeypatch, pages)

        plan = collect_supervisor_plan(scholarship)
        outcome = persist_supervisor_plan(db, scholarship, plan)

        coverage = db.execute(select(ScholarshipSupervisorCoverage)).scalars().one()
        assert coverage.status == "no_verified_supervisor_found"
        assert coverage.verified_supervisor_count == 0
        assert outcome.status == "no_verified_supervisor_found"


# ---------------------------------------------------------------------------
# G/H. Idempotency and survival of existing rows
# ---------------------------------------------------------------------------


class TestIdempotencyAndSurvival:
    def test_g_rerunning_the_same_discovery_is_idempotent(self, db, monkeypatch):
        """G. A repeated bounded run converges on one row, not two."""
        scholarship = _scholarship(db)
        _serve(monkeypatch, _profile(VALID_PROFILE))

        first = discover_for_scholarship(db, scholarship)
        after_first = _counts(db)
        second = discover_for_scholarship(db, scholarship)
        after_second = _counts(db)

        assert after_first["professors"] == after_second["professors"]
        assert after_first["links"] == after_second["links"]
        assert after_first["coverage"] == after_second["coverage"]
        assert first.professors_found == second.professors_found
        # The count is recomputed from the links, never incremented, so it cannot
        # drift upward on a repeat run.
        coverage = db.execute(select(ScholarshipSupervisorCoverage)).scalars().one()
        assert coverage.verified_supervisor_count == after_second["links"]

    def test_h_existing_valid_rows_survive_a_later_failed_candidate(self, db, monkeypatch):
        """H. A refused candidate must not take a good professor with it."""
        scholarship = _scholarship(db)
        _serve(monkeypatch, _profile(VALID_PROFILE))
        discover_for_scholarship(db, scholarship)
        assert _names(db) == ["Ada Lovelace", "Grace Hopper"]

        # A second run in which the directory now lists nothing that qualifies.
        pages = _profile(VALID_PROFILE)
        pages[f"https://{UNIVERSITY}/people/faculty"] = ALL_INVALID_DIRECTORY
        _serve(monkeypatch, pages)
        plan = collect_supervisor_plan(scholarship)
        persist_supervisor_plan(db, scholarship, plan)

        assert _names(db) == ["Ada Lovelace", "Grace Hopper"], (
            "a failing candidate run must not delete professors found earlier"
        )
        assert _counts(db)["links"] == 2

    def test_h_a_refused_candidate_leaves_no_partial_row(self, db):
        """H. No half-written professor, link, evidence or availability row."""
        from app.models_supervisor import ProfessorAvailability, SupervisorSourceEvidence
        from app.services.supervisor_discovery import FacultyCandidate

        scholarship = _scholarship(db)
        decision = approve_candidate_set(
            [
                FacultyCandidate(
                    name="Academic Staff",
                    profile_url=f"https://{UNIVERSITY}/people/academic-staff",
                    role="academic",
                    role_evidence="inline_role",
                )
            ],
            seed_host=UNIVERSITY,
            faculty_url=f"https://{UNIVERSITY}/people/faculty",
            seen_urls=set(),
        )
        group = ApprovedCandidateGroup(
            faculty_url=f"https://{UNIVERSITY}/people/faculty",
            directory_html="<html></html>",
            http_status=200,
            discovery_path="static",
            approved=decision.approved,
            examined=decision.examined,
            rejected=decision.rejected,
        )
        persist_supervisor_plan(db, scholarship, _plan_with(group, scholarship.id))

        for model in (
            ProfessorProfile,
            ScholarshipProfessorLink,
            SupervisorSourceEvidence,
            ProfessorAvailability,
        ):
            assert db.execute(select(func.count(model.id))).scalar_one() == 0, (
                f"{model.__tablename__} received a row for a refused candidate"
            )


def _plan_with(group: ApprovedCandidateGroup, scholarship_id: int):
    from app.services.supervisor_discovery import SupervisorDiscoveryPlan

    return SupervisorDiscoveryPlan(
        scholarship_id=scholarship_id,
        status="",
        groups=(group,),
        examined_count=group.examined,
        rejected_count=group.rejected,
    )


# ---------------------------------------------------------------------------
# I/J. The transaction boundary, and no hidden commit
# ---------------------------------------------------------------------------


class TestTransactionBoundary:
    def test_i_nothing_is_committed_until_the_persistence_boundary(self, db, monkeypatch):
        """I. Collection issues no commit at all.

        A session spy that fails the test on any commit, so a commit reintroduced
        into the pre-gating path fails here rather than passing quietly. The spy
        stays installed across both stages so the commit count can be compared at
        the boundary.
        """
        scholarship = _scholarship(db)
        _serve(monkeypatch, _profile(VALID_PROFILE))

        commits: list[int] = []
        real_commit = type(db).commit

        def counting_commit(self, *args, **kwargs):
            commits.append(1)
            return real_commit(self, *args, **kwargs)

        original = db.commit
        db.commit = counting_commit.__get__(db, type(db))
        try:
            plan = collect_supervisor_plan(scholarship)
            assert plan.approved_count == 2
            assert commits == [], "collection committed before gating was persisted"

            before = len(commits)
            persist_supervisor_plan(db, scholarship, plan)
            # The boundary writes, and it writes at least once.
            assert len(commits) > before, "the persistence boundary must commit"
            assert _counts(db)["professors"] == 2
        finally:
            db.commit = original

    def test_i_coverage_is_updated_at_the_boundary_and_not_before(self, db, monkeypatch):
        """I. The coverage row does not exist while classification is running."""
        scholarship = _scholarship(db)
        _serve(monkeypatch, _profile(VALID_PROFILE))

        plan = collect_supervisor_plan(scholarship)
        assert _counts(db)["coverage"] == 0, (
            "a coverage row was created before the candidate set was known"
        )

        persist_supervisor_plan(db, scholarship, plan)
        assert _counts(db)["coverage"] == 1

    def test_j_the_persistence_function_refuses_an_unapproved_candidate(self, db):
        """J. The gate is structural, not a matter of discipline.

        ``persist_approved_candidates`` accepts only
        ``ApprovedSupervisorCandidate``. Handing it a raw candidate raises, so
        there is no path to an insert that skips the gate without also being an
        error someone would notice.
        """
        from app.services.supervisor_discovery import (
            FacultyCandidate,
            persist_approved_candidates,
        )

        scholarship = _scholarship(db)
        raw = FacultyCandidate(
            name="Grace Hopper",
            profile_url=f"https://{UNIVERSITY}/people/grace-hopper",
            role="professor",
            role_evidence="profile_role",
        )
        group = ApprovedCandidateGroup(
            faculty_url=f"https://{UNIVERSITY}/people/faculty",
            directory_html="<html></html>",
            http_status=200,
            discovery_path="static",
            approved=(raw,),  # deliberately wrong type
        )
        with pytest.raises(TypeError, match="ApprovedSupervisorCandidate"):
            persist_approved_candidates(db, scholarship, group, "Test University")

        assert _counts(db)["professors"] == 0

    def test_j_an_approved_candidate_is_a_distinct_type_from_a_raw_one(self):
        """J. The two types are not interchangeable, and not one of the other."""
        from app.services.supervisor_discovery import FacultyCandidate

        approved = ApprovedSupervisorCandidate(
            candidate=FacultyCandidate(
                name="Grace Hopper",
                profile_url=f"https://{UNIVERSITY}/people/grace-hopper",
                role="professor",
                role_evidence="profile_role",
            ),
            faculty_url=f"https://{UNIVERSITY}/people/faculty",
            normalized_name="grace hopper",
            normalized_url=f"https://{UNIVERSITY}/people/grace-hopper",
            verification_status="verified",
            role_evidence="profile_role",
        )
        assert approved.is_verified is True
        assert not isinstance(approved.candidate, ApprovedSupervisorCandidate)


# ---------------------------------------------------------------------------
# The recorded real-source evidence, run through the new gate
#
# Cornell University, https://www.cs.cornell.edu/directory, read by the pipeline
# on the record. No network here: these are the sixteen labels that page actually
# produced, with the URLs it served them from.
# ---------------------------------------------------------------------------

CORNELL_DIRECTORY = "https://www.cs.cornell.edu/directory"
CORNELL_SEED_HOST = "www.cs.cornell.edu"

#: The fourteen real people that directory yielded. On the listing page each is a
#: bare name at a personal-profile path: personhood is established by structure,
#: and **no role is stated**. Their profile pages supply the role afterwards.
CORNELL_PEOPLE = (
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
)

#: The two labels that are not people. The fragment case matters: a `#` anchor is
#: enough to turn a navigation link into a "profile".
CORNELL_NAVIGATION_LABELS = (
    ("Academic Planning", f"{CORNELL_DIRECTORY}#grad"),
    ("Academic Staff", f"{CORNELL_DIRECTORY}/academic-staff"),
)


class TestTheRecordedRealSourceEvidence:
    """The gate, applied to what the real directory actually produced.

    This is the offline half of the real-source proof. It cannot re-fetch Cornell,
    so it does not claim to: it pins the *recorded* result through the new gate, so
    that a change to the gate which broke the real case would fail here rather than
    waiting for a production run to discover it.
    """

    def _profile_url(self, name: str) -> str:
        return f"{CORNELL_DIRECTORY}/{name.lower().replace(' ', '-')}"

    def test_all_fourteen_people_pass_the_gate_once_a_profile_states_a_role(self):
        candidates = [
            _candidate(name, self._profile_url(name), "professor", "profile_role")
            for name in CORNELL_PEOPLE
        ]
        decision = approve_candidate_set(
            candidates,
            seed_host=CORNELL_SEED_HOST,
            faculty_url=CORNELL_DIRECTORY,
            seen_urls=set(),
        )
        assert len(decision.approved) == len(CORNELL_PEOPLE), (
            f"the gate dropped a real academic: "
            f"{sorted(set(CORNELL_PEOPLE) - {c.name for c in decision.approved})}"
        )
        assert decision.rejected == 0
        assert all(c.is_verified for c in decision.approved)

    def test_the_fourteen_are_refused_while_the_role_is_unproven(self):
        """The same fourteen, at the point where personhood is all that is known.

        This is the state the real directory reached before the profile stage ran,
        and it is why a production proof may not report VERIFIED merely because
        personhood passed.
        """
        candidates = [
            _candidate(name, self._profile_url(name), None, "source_context")
            for name in CORNELL_PEOPLE
        ]
        decision = approve_candidate_set(
            candidates,
            seed_host=CORNELL_SEED_HOST,
            faculty_url=CORNELL_DIRECTORY,
            seen_urls=set(),
        )
        assert decision.approved == (), "no role stated means no professor"
        assert decision.rejected == len(CORNELL_PEOPLE)
        assert all(
            decision.rejection_reasons.get(str(SupervisorGate.ROLE_EVIDENCE)) == len(CORNELL_PEOPLE)
            for _ in (0,)
        )

    @pytest.mark.parametrize("label,url", CORNELL_NAVIGATION_LABELS)
    def test_neither_navigation_label_passes_the_gate(self, label, url):
        """The two false positives from the real directory, by hand.

        Built by hand rather than extracted, so this fails even if the classifier
        upstream changes, or a future caller constructs such a candidate directly.
        """
        candidate = _candidate(label, url, "academic", "inline_role")
        verdict = verify_supervisor_candidate(
            candidate, seed_host=CORNELL_SEED_HOST, faculty_url=CORNELL_DIRECTORY
        )
        assert not verdict.approved, f"{label!r} is a navigation label, not a person"
        assert verification_status_for(candidate) != "verified"

    def test_cornell_is_recognised_as_an_institutional_domain(self):
        """The seed host clears the domain gate on its own merits."""
        from app.services.supervisor_gating import host_is_official, same_institution

        assert host_is_official(CORNELL_SEED_HOST) is True
        assert same_institution(CORNELL_SEED_HOST, CORNELL_DIRECTORY) is True


# ---------------------------------------------------------------------------
# Regression guards on the code's shape
#
# These read the source rather than the behaviour. Behaviour is what must be
# true; shape is what stops it being silently un-true by a later edit that is
# individually reasonable.
# ---------------------------------------------------------------------------


def _function_nodes(source: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _calls_in(node: ast.AST) -> set[str]:
    """Return every method/attribute name called inside ``node``."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute):
                names.add(func.attr)
            elif isinstance(func, ast.Name):
                names.add(func.id)
    return names


class TestPersistenceIsNotReintroducedBeforeGating:
    COLLECTION_FUNCTIONS = (
        "collect_supervisor_plan",
        "approve_candidate_set",
        "verify_supervisor_candidate",
        "extract_faculty_candidates",
        "_collect_render_for_shells",
    )

    @pytest.mark.parametrize("function_name", COLLECTION_FUNCTIONS)
    def test_collection_functions_call_no_write(self, function_name):
        """No database verb appears anywhere in the pre-persistence stage.

        The list is verb-level (``commit``, ``flush``, ``execute``, ...) rather
        than receiver-level: ``set.add`` is a perfectly legitimate call in this
        stage, and an ``add`` ban would be noise that a future author works around
        instead of respecting.
        """
        for source_path in (GATING_SOURCE, DISCOVERY_SOURCE):
            nodes = _function_nodes(source_path.read_text(encoding="utf-8"))
            if function_name not in nodes:
                continue
            calls = _calls_in(nodes[function_name])
            for forbidden in ("commit", "flush", "execute", "merge", "delete"):
                assert forbidden not in calls, (
                    f"{function_name} calls {forbidden}(); the pre-persistence stage "
                    "must not touch the database"
                )
            # And it holds no session to touch one with.
            for node in ast.walk(nodes[function_name]):
                if isinstance(node, ast.Name):
                    assert node.id not in ("db", "session"), (
                        f"{function_name} references {node.id!r}; the pre-persistence "
                        "stage must have no session in scope"
                    )
            return
        pytest.fail(f"{function_name} disappeared; update this guard")

    def test_discover_for_scholarship_collects_before_it_persists(self):
        """The ordering is asserted on the call graph, not in a comment."""
        source = DISCOVERY_SOURCE.read_text(encoding="utf-8")
        nodes = _function_nodes(source)
        calls = [
            child.func.id
            for child in ast.walk(nodes["discover_for_scholarship"])
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        ]
        assert "collect_supervisor_plan" in calls
        assert "persist_supervisor_plan" in calls
        assert calls.index("collect_supervisor_plan") < calls.index(
            "persist_supervisor_plan"
        ), "discovery must collect before it persists"

    def test_discover_for_scholarship_does_not_write_directly(self):
        """No commit, flush or add anywhere in the public entry point."""
        source = DISCOVERY_SOURCE.read_text(encoding="utf-8")
        node = _function_nodes(source)["discover_for_scholarship"]
        calls = _calls_in(node)
        for forbidden in ("commit", "flush", "add", "execute"):
            assert forbidden not in calls, (
                f"discover_for_scholarship calls {forbidden}(); persistence belongs "
                "to persist_supervisor_plan, at one boundary"
            )

    def test_the_write_path_is_identified_and_bounded(self):
        """Every ``db.commit`` in the module belongs to a named boundary.

        If this fails, a commit has been added somewhere unaccounted for, which is
        exactly how the original design leaked writes back into the fetch loop.
        """
        source = DISCOVERY_SOURCE.read_text(encoding="utf-8")
        nodes = _function_nodes(source)
        committing = {
            name for name, node in nodes.items() if "commit" in _calls_in(node)
        }
        assert committing <= {
            "persist_supervisor_plan",
            "_discover_one",
        }, f"unexpected commit in {sorted(committing - {'persist_supervisor_plan', '_discover_one'})}"

    def test_no_coverage_row_is_written_by_the_collect_stage(self):
        """``ensure_coverage_row`` may not be reachable from collection."""
        source = DISCOVERY_SOURCE.read_text(encoding="utf-8")
        nodes = _function_nodes(source)
        assert "ensure_coverage_row" not in _calls_in(nodes["collect_supervisor_plan"])
