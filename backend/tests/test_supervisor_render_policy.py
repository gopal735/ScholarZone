"""Rendering policy: deterministic fixtures, no public internet.

Covers the source taxonomy, JS-shell classification, barrier detection, bounds and
the static-first guarantee. The network boundary is mocked; the classifier, the
outcome mapping and the budget enforcement all run for real.

An autouse guard blocks any socket that is not loopback, so a test in this module
cannot quietly reach the public internet. That is the mechanism behind "unit
tests must not access the real Internet" rather than a promise in a comment.
"""

from __future__ import annotations

import os
import socket

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base, Scholarship  # noqa: E402
from app.models_supervisor import ProfessorProfile, ScholarshipProfessorLink  # noqa: E402
from app.services import supervisor_render as render_module  # noqa: E402
from app.services import supervisor_discovery as worker  # noqa: E402
from app.services.supervisor_jsdetect import (  # noqa: E402
    classify_shell,
    looks_like_directory_listing,
    render_href_allowed,
)
from app.services.supervisor_source import (  # noqa: E402
    ACCESS_BARRIER_KINDS,
    NON_CONCLUSIVE_OUTCOMES,
    RenderBudget,
    RenderErrorKind,
    SourceOutcome,
    detect_access_barrier,
)

ACADEMIC_SUFFIXES = (".edu", ".ac.uk", ".edu.au")


@pytest.fixture(autouse=True)
def no_public_network(monkeypatch):
    """Fail loudly if a test in this module opens a non-loopback socket."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if isinstance(host, str) and not (
            host.startswith("127.") or host in ("localhost", "::1", "0.0.0.0")
        ):
            raise AssertionError(f"unexpected public network access: {host}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield


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


# ---------------------------------------------------------------------------
# Fixtures: every source shape that has to be classified
# ---------------------------------------------------------------------------

SSR_DIRECTORY = """
<html><head><title>Faculty of Computing</title></head><body>
<h1>Faculty of Computing</h1>
<p>Academic staff in the School of Computing and Information Systems.</p>
<ul>
  <li><a href="/people/ada-lovelace">Dr Ada Lovelace</a></li>
  <li><a href="/people/alan-turing">Professor Alan Turing</a></li>
</ul>
</body></html>
"""

EMPTY_DIRECTORY = """
<html><head><title>Faculty of Computing</title></head><body>
<h1>Faculty of Computing</h1>
<p>No academic staff are currently listed for this school.</p>
<p>The faculty group is being restructured and this section is not maintained.</p>
</body></html>
"""

JS_SHELL = (
    '<html><head><title>People</title></head><body><nav><a href="/">Home</a></nav>'
    '<div id="app"></div><script src="/_next/static/chunks/main.js"></script>'
    "</body></html>"
)

RENDERED_DIRECTORY = """
<html><head><title>Faculty</title></head><body><h1>Faculty</h1>
<ul>
  <li><a href="/people/ada-lovelace">Dr Ada Lovelace</a> <span>Professor of Computer Science</span></li>
  <li><a href="/people/alan-turing">Professor Alan Turing</a> <span>Reader in Logic</span></li>
</ul></body></html>
"""

INFINITE_SCROLL_DIRECTORY = """
<html><head><title>Directory</title></head><body><h1>Directory</h1>
<div id="grid"><a href="/people/a">Dr A One</a></div>
<button id="more">Load more</button></body></html>
"""

LOGIN_PAGE = (
    '<html><head><title>Staff Directory - Sign In</title></head><body>'
    '<form action="/sso/login" method="post">'
    '<input type="text" name="user"><input type="password" name="pass">'
    "</form></body></html>"
)

CHALLENGE_PAGE = (
    '<html><head><title>Just a moment...</title></head><body>'
    '<div class="cf_chl_opt"></div></body></html>'
)

TURNSTILE_PAGE = (
    '<html><head><title>Verify</title></head><body>'
    '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>'
    "</body></html>"
)

RECAPTCHA_PAGE = (
    '<html><body><script src="https://www.google.com/recaptcha/api.js"></script>'
    '<div class="g-recaptcha" data-sitekey="x"></div></body></html>'
)


# ---------------------------------------------------------------------------
# Part 3: JS-shell classification
# ---------------------------------------------------------------------------


def test_a_real_javascript_shell_is_classified_as_one():
    verdict = classify_shell(JS_SHELL)

    assert verdict.is_shell is True
    assert "empty_app_container" in verdict.signals


@pytest.mark.parametrize("page", [SSR_DIRECTORY, EMPTY_DIRECTORY, LOGIN_PAGE])
def test_ordinary_pages_are_not_classified_as_shells(page):
    # The load-bearing negative: an empty directory is a true negative, and calling
    # it a shell would send a browser after a page that never needed one.
    assert classify_shell(page).is_shell is False


def test_sparse_text_alone_does_not_make_a_shell():
    # A short but genuine page: sparse text with no other shell evidence.
    page = "<html><body><h1>Contact</h1><p>Email the office.</p></body></html>"

    assert classify_shell(page).is_shell is False


def test_a_next_data_hydration_blob_with_no_content_is_a_shell():
    page = '<html><body><div id="__next"></div><script id="__NEXT_DATA__">{"props":{}}</script></body></html>'

    verdict = classify_shell(page)

    assert verdict.is_shell is True
    assert "hydration_state" in verdict.signals


def test_a_server_rendered_hydration_page_is_not_a_shell():
    # Next.js pages often carry __NEXT_DATA__ *and* full server-rendered content.
    # Treating that as a shell would double-render every SSR page.
    page = (
        '<html><body><h1>Faculty</h1><ul><li><a href="/people/a">Dr A One</a></li></ul>'
        '<script id="__NEXT_DATA__">{"props":{}}</script></body></html>'
    )

    assert classify_shell(page).is_shell is False


def test_the_verdict_explains_itself():
    verdict = classify_shell(JS_SHELL)

    assert verdict.signals
    assert "empty_app_container" in verdict.reason


# ---------------------------------------------------------------------------
# Part 17/18: barriers are detected, never circumvented
# ---------------------------------------------------------------------------


def test_login_gated_page_is_detected():
    kind, marker = detect_access_barrier(LOGIN_PAGE)

    assert kind == "login_required"
    assert marker in ("password_field", "login_form", "sign_in_language")


@pytest.mark.parametrize(
    "page,marker",
    [
        (CHALLENGE_PAGE, "cloudflare_challenge"),
        (TURNSTILE_PAGE, "cloudflare_turnstile"),
        (RECAPTCHA_PAGE, "recaptcha"),
    ],
)
def test_anti_bot_challenges_are_detected(page, marker):
    kind, found = detect_access_barrier(page)

    assert kind == "anti_bot_challenge"
    assert found == marker


def test_an_anti_bot_page_is_not_misreported_as_a_login_page():
    # A challenge often also contains sign-in language. Reporting that as "login
    # required" invites somebody to try authenticating against a challenge page,
    # which is the wrong next step entirely.
    kind, _ = detect_access_barrier(CHALLENGE_PAGE)

    assert kind == "anti_bot_challenge"


def test_a_normal_directory_is_not_a_barrier():
    assert detect_access_barrier(RENDERED_DIRECTORY) is None


def test_barrier_kinds_are_access_denials():
    assert RenderErrorKind.LOGIN_REQUIRED in ACCESS_BARRIER_KINDS
    assert RenderErrorKind.ANTI_BOT_CHALLENGE in ACCESS_BARRIER_KINDS
    assert RenderErrorKind.NAVIGATION_TIMEOUT not in ACCESS_BARRIER_KINDS


def test_a_sparse_directory_with_no_role_bearing_links_is_not_statically_readable():
    """Regression from a real institution.

    The University of Adelaide's directory measured a 0.039 text ratio with no
    `id="app"` container and an inline script share below the heavy threshold, so
    every other signal abstained and the page was classified as statically
    readable. Recording that as a negative would have told a student the
    university employs nobody, on the evidence that the crawler never saw its
    staff list.

    The fix is not a special case for Adelaide. It is the general observation
    that a page presenting itself as a people directory, with almost no readable
    text and not one link that names an academic, has not told us who works
    there.
    """
    page = (
        "<html><head><title>People | Adelaide</title>"
        "<meta name='description' content='Find staff and students at the University of Adelaide.'>"
        "<link rel='stylesheet' href='/etc.clientlibs/adelaide/clientlibs/site.css'>"
        "</head><body>"
        "<nav><a href='/'>Home</a><a href='/study'>Study</a><a href='/research'>Research</a></nav>"
        "<h1>People</h1>"
        "<div id='content'></div>"
        "<a href='/people/'>People</a>"
        "<a href='/life-at-adelaide/adelaide-and-south-australia/'>South Australia</a>"
        "<script src='/etc.clientlibs/adelaide/clientlibs/site.js'></script>"
        # Padded with markup so the visible-text ratio matches the real page,
        # which measured 0.039. A short fixture would pass the directory test for
        # the wrong reason - it would be sparse enough to trip the text signal on
        # its own, hiding whether the directory signal works.
        + "".join(
            f"<!-- asset manifest entry {index} -->"
            for index in range(40)
        )
        + "</body></html>"
    )
    verdict = classify_shell(page)

    assert verdict.needs_more_than_static is True
    assert "directory_without_entries" in verdict.signals


def test_a_directory_with_prose_explaining_itself_is_still_a_true_negative():
    # The other side of the same rule: a directory that says it lists nobody is
    # a genuine negative, and must not be sent to a browser.
    assert classify_shell(EMPTY_DIRECTORY).needs_more_than_static is False


def test_a_directory_with_academic_links_is_not_a_shell():
    assert classify_shell(SSR_DIRECTORY).needs_more_than_static is False
    assert classify_shell(RENDERED_DIRECTORY).needs_more_than_static is False


# ---------------------------------------------------------------------------
# Part 1/11: outcome taxonomy
# ---------------------------------------------------------------------------


def test_every_non_conclusive_outcome_is_excluded_from_a_negative():
    for outcome in (
        SourceOutcome.SOURCE_REQUIRES_RENDERING,
        SourceOutcome.SOURCE_BLOCKED,
        SourceOutcome.INVALID_SOURCE,
        SourceOutcome.ERROR,
    ):
        assert outcome in NON_CONCLUSIVE_OUTCOMES
    assert SourceOutcome.NOT_FOUND_WITHIN_SEARCH_SCOPE not in NON_CONCLUSIVE_OUTCOMES


def test_the_error_taxonomy_does_not_collapse_to_a_negative():
    kinds = {member.value for member in RenderErrorKind}

    assert "no_professor_found" not in kinds
    assert len(kinds) >= 12, "the taxonomy must stay granular"


def test_a_source_outcome_only_concludes_when_it_is_a_true_negative():
    def conclusive(outcome: SourceOutcome) -> bool:
        return outcome == SourceOutcome.NOT_FOUND_WITHIN_SEARCH_SCOPE

    assert conclusive(SourceOutcome.NOT_FOUND_WITHIN_SEARCH_SCOPE) is True
    for outcome in NON_CONCLUSIVE_OUTCOMES:
        assert conclusive(outcome) is False


# ---------------------------------------------------------------------------
# Part 5/33: bounds
# ---------------------------------------------------------------------------


def test_the_budget_has_no_unbounded_dimension():
    budget = RenderBudget()

    for field in (
        "total_seconds",
        "navigation_timeout_ms",
        "max_pages",
        "max_pagination_steps",
        "max_scroll_iterations",
        "max_candidates",
        "max_content_bytes",
        "max_redirects",
        "max_concurrent_contexts",
        "max_browser_jobs",
    ):
        value = getattr(budget, field)
        assert value is not None
        assert value < float("inf"), f"{field} must be finite"


def test_the_budget_names_the_bound_that_was_hit():
    budget = RenderBudget(max_pages=3, max_candidates=10)

    assert budget.budget_exhausted_reason(pages=3) == "max_pages"
    assert budget.budget_exhausted_reason(candidates=10) == "max_candidates"
    assert budget.budget_exhausted_reason(pages=2, candidates=1) is None
    assert budget.budget_exhausted_reason(total_seconds=1e9) == "total_seconds"


def test_defaults_are_small_enough_to_be_safe():
    budget = RenderBudget()

    assert budget.max_pages <= 10
    assert budget.max_candidates <= 50
    assert budget.total_seconds <= 120
    assert budget.max_concurrent_contexts <= 4
    assert budget.max_browser_jobs <= 10


# ---------------------------------------------------------------------------
# Part 31: static-first
# ---------------------------------------------------------------------------


def test_rendering_is_off_unless_an_operator_enables_it(monkeypatch):
    monkeypatch.delenv(render_module.RENDER_ENABLED_ENV, raising=False)
    assert render_module.rendering_enabled() is False

    monkeypatch.setenv(render_module.RENDER_ENABLED_ENV, "true")
    assert render_module.rendering_enabled() is True


def test_a_disabled_driver_reports_rendering_rather_than_failure():
    import asyncio

    driver = render_module.NullRenderDriver("disabled")

    observation = asyncio.run(
        driver.render("https://uni1.edu/people", budget=RenderBudget(), seed_host="uni1.edu")
    )

    assert observation.outcome == SourceOutcome.SOURCE_REQUIRES_RENDERING
    assert observation.error_kind == RenderErrorKind.DISABLED_BY_CONFIG


def test_an_ssr_directory_is_not_sent_to_the_browser(monkeypatch, db):
    """Static-first, proven: a page that answers over HTTP never launches a browser."""
    from app.services.official_source_fetcher import OfficialSourceFetchResult

    def served(url: str):
        if "/people/faculty" in url:
            return OfficialSourceFetchResult(
                success=True, status_code=200, final_url=url, content=SSR_DIRECTORY
            )
        return OfficialSourceFetchResult(
            success=True,
            status_code=200,
            final_url=url,
            content='<html><body><h1>MSc</h1><a href="/people/faculty">Our Faculty</a></body></html>',
        )

    monkeypatch.setattr(worker, "polite_fetch", served)
    worker.clear_robots_cache()

    def explode(*args, **kwargs):
        raise AssertionError("the browser must not be launched for a server-rendered source")

    monkeypatch.setattr(render_module, "render_blocking", explode)
    monkeypatch.setenv(render_module.RENDER_ENABLED_ENV, "true")

    row = Scholarship(
        title="MSc",
        country="UK",
        degree="Master",
        funding="Fully Funded",
        description="d",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        coverage=[],
        requirements=[],
        documents=[],
        official_source="U",
        official_source_url="https://uni1.edu/p",
        is_verified=True,
        verification_status="active",
        image_url="https://uni1.edu/l.png",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    outcome = worker.discover_for_scholarship(
        db, row, render_budget=RenderBudget(total_seconds=30.0)
    )

    assert outcome.status == "verified_supervisors"
    assert db.query(ProfessorProfile).count() == 2


def test_a_rendered_page_goes_through_the_same_role_gate(monkeypatch, db):
    """A rendered directory still needs a stated academic role."""
    from app.services.official_source_fetcher import OfficialSourceFetchResult
    from app.services.supervisor_source import SourceObservation

    def served(url: str):
        if "/people/faculty" in url:
            return OfficialSourceFetchResult(
                success=True, status_code=200, final_url=url, content=JS_SHELL
            )
        return OfficialSourceFetchResult(
            success=True,
            status_code=200,
            final_url=url,
            content='<html><body><h1>MSc</h1><a href="/people/faculty">Our Faculty</a></body></html>',
        )

    monkeypatch.setattr(worker, "polite_fetch", served)
    worker.clear_robots_cache()

    # Rendered HTML that lists people with no academic role anywhere.
    roleless = (
        '<html><body><h1>Faculty</h1><ul>'
        '<li><a href="/people/ada-lovelace">Ada Lovelace</a></li>'
        '<li><a href="/people/south-australia">South Australia</a></li>'
        "</ul></body></html>"
    )
    monkeypatch.setattr(
        render_module,
        "render_blocking",
        lambda url, **kwargs: SourceObservation(
            url=url, outcome=SourceOutcome.SUCCESS, html=roleless, discovery_path="browser_render"
        ),
    )

    row = Scholarship(
        title="MSc",
        country="UK",
        degree="Master",
        funding="Fully Funded",
        description="d",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        coverage=[],
        requirements=[],
        documents=[],
        official_source="U",
        official_source_url="https://uni1.edu/p",
        is_verified=True,
        verification_status="active",
        image_url="https://uni1.edu/l.png",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    outcome = worker.discover_for_scholarship(
        db, row, render_budget=RenderBudget(total_seconds=30.0)
    )

    # Neither the person without a role nor the place name becomes a professor.
    assert db.query(ProfessorProfile).count() == 0
    assert outcome.status == "source_requires_rendering"


# ---------------------------------------------------------------------------
# Part 6/34: one-domain boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,allowed",
    [
        ("https://uni1.edu/people/ada", True),
        ("https://staff.uni1.edu/people/ada", True),
        ("https://www.uni1.edu/people/ada", True),
        ("https://evil-uni1.example/people/ada", False),
        ("https://linkedin.com/in/someone", False),
        ("https://facebook.com/someone", False),
        ("https://www.google.com/search?q=professor", False),
        ("javascript:void(0)", False),
        ("file:///etc/passwd", False),
    ],
)
def test_the_browser_stays_inside_the_institution(url, allowed):
    assert render_href_allowed(url, "uni1.edu", ACADEMIC_SUFFIXES) is allowed


def test_a_profile_on_a_third_party_domain_is_not_official_evidence():
    from app.services.supervisor_person import classify_person_candidate

    # The name and role are perfect; the domain is not the institution's.
    signal = classify_person_candidate(
        "Dr Jane Smith", url="https://scholarpad.example/jane-smith", directory_context=True
    )

    assert signal is not None, "the person evidence itself is fine"
    # Which is precisely why the domain check is separate and mandatory.
    assert render_href_allowed("https://scholarpad.example/jane-smith", "uni1.edu", ACADEMIC_SUFFIXES) is False


# ---------------------------------------------------------------------------
# Part 35: role evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,accepted",
    [
        ("Dr Jane Smith", True),
        ("Professor Alan Turing", True),
        ("Associate Professor A Person", True),
        ("Research Fellow R Person", True),
        ("Jane Smith â€” Lecturer in Physics", True),
        ("Admissions Officer", False),
        ("Student", False),
        ("Alumni Relations Team", False),
    ],
)
def test_role_vocabulary_is_centrally_defined_and_applied(label, accepted):
    from app.services.supervisor_person import academic_role_in

    found = academic_role_in(label)

    if accepted:
        assert found is not None, f"{label!r} should name an academic role"
    else:
        assert found is None or found in ("academic",), f"{label!r} should not name a research role"


def test_the_browser_path_uses_the_same_role_vocabulary():
    # One definition of "academic role", imported by both tiers. A second
    # vocabulary here is how the browser quietly becomes a looser door.
    assert render_module.__name__.endswith("supervisor_render")
    from app.services import supervisor_person

    assert hasattr(supervisor_person, "academic_role_in")
    assert "academic_role_in" in worker.__dict__


# ---------------------------------------------------------------------------
# Part 40: duplicates
# ---------------------------------------------------------------------------


def test_the_same_person_from_two_paths_is_stored_once(db):
    from app.services.supervisor_discovery import upsert_professor

    candidate = worker.FacultyCandidate(
        name="Ada Lovelace",
        profile_url="https://uni1.edu/people/ada-lovelace",
        role="professor",
        role_evidence="honorific",
    )
    row = Scholarship(
        title="MSc",
        country="UK",
        degree="Master",
        funding="Fully Funded",
        description="d",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        coverage=[],
        requirements=[],
        documents=[],
        official_source="U",
        official_source_url="https://uni1.edu/p",
        is_verified=True,
        verification_status="active",
        image_url="https://uni1.edu/l.png",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    first = upsert_professor(db, candidate, institution_name="U", source_type="official_department_page")
    db.commit()
    second = upsert_professor(db, candidate, institution_name="U", source_type="official_department_page")
    db.commit()

    assert first.id == second.id
    assert db.query(ProfessorProfile).count() == 1


def test_a_duplicate_relationship_is_refused_by_the_database(db):
    from app.services.supervisor_discovery import upsert_link

    professor = ProfessorProfile(
        canonical_name="Ada Lovelace",
        institution_name="U",
        official_profile_url="https://uni1.edu/people/ada",
    )
    db.add(professor)
    db.commit()
    db.refresh(professor)
    row = Scholarship(
        title="MSc",
        country="UK",
        degree="Master",
        funding="Fully Funded",
        description="d",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        coverage=[],
        requirements=[],
        documents=[],
        official_source="U",
        official_source_url="https://uni1.edu/p",
        is_verified=True,
        verification_status="active",
        image_url="https://uni1.edu/l.png",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    from sqlalchemy.exc import IntegrityError

    for _ in range(2):
        try:
            upsert_link(
                db,
                row,
                professor,
                relationship_type="potential_supervisor",
                evidence_url="https://uni1.edu/people",
                evidence_type="official_department_page",
                summary="s",
                verification_status="verified",
            )
            db.commit()
        except IntegrityError:
            db.rollback()

    assert db.query(ScholarshipProfessorLink).count() == 1


# ---------------------------------------------------------------------------
# Part 11: directory classification
# ---------------------------------------------------------------------------


def test_a_rendered_directory_is_recognised_as_a_directory():
    assert looks_like_directory_listing(RENDERED_DIRECTORY) is True
    assert looks_like_directory_listing(EMPTY_DIRECTORY) is True
    assert looks_like_directory_listing("<html><body><p>Map</p></body></html>") is False


def test_the_infinite_scroll_fixture_is_a_directory():
    assert looks_like_directory_listing(INFINITE_SCROLL_DIRECTORY) is True
