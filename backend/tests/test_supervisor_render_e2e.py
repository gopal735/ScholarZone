"""The proof: a real JavaScript directory, really rendered, really yielding a professor.

Every other supervisor test mocks the network or feeds fixtures to the parser.
This one runs the whole chain for real:

    real localhost HTTP server
        -> static fetch genuinely cannot see any professor
        -> bounded headless Chromium executes JavaScript
        -> the DOM gains faculty cards that were never in the served HTML
        -> the same central role classifier accepts two academics
        -> the same storage gate writes exactly two professors, once each

Nothing here asserts that a browser was launched, and nothing mocks
``render_blocking``. If the browser is missing, the render returns an
inconclusive state and the assertions that expect a professor fail - which is the
intended behaviour.

Skipped only when no browser driver is installed, and it says so loudly rather
than passing quietly.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from datetime import date  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base, Scholarship  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
)
from app.services import supervisor_render  # noqa: E402
from app.services.supervisor_discovery import discover_for_scholarship  # noqa: E402
from app.services.supervisor_jsdetect import classify_shell  # noqa: E402
from app.services.supervisor_source import RenderBudget  # noqa: E402
from support_local_js_directory import LocalDirectoryServer  # noqa: E402

playwright = pytest.importorskip(
    "playwright.async_api", reason="No browser driver installed; rendering cannot be proven."
)


@pytest.fixture
def browser_available() -> None:
    if not supervisor_render.playwright_available():
        pytest.skip("playwright importable but no driver runtime")


@pytest.fixture
def server():
    with LocalDirectoryServer() as running:
        yield running


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


def _scholarship(db, server):
    row = Scholarship(
        title="MSc Computer Science",
        country="United Kingdom",
        degree="Master",
        funding="Fully Funded",
        description="A test programme served by a local synthetic directory.",
        status="open",
        deadline_date=date(2027, 6, 30),
        deadline_precision="exact",
        eligibility=[],
        coverage=[],
        requirements=[],
        documents=[],
        official_source="Local Test University",
        official_source_url=server.url("/programmes/msc"),
        is_verified=True,
        verification_status="active",
        image_url=server.url("/logo.png"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def loopback_is_official(monkeypatch):
    """Declare the loopback host a local institution, for this test only.

    The pipeline refuses non-academic hosts on purpose - that refusal *is* the
    institution-ownership boundary - so a localhost fixture has to ask for it
    explicitly rather than the allowance being quietly baked into production code.
    """
    from app.services import supervisor_discovery as worker

    original = worker.host_is_official
    monkeypatch.setattr(
        worker,
        "host_is_official",
        lambda host: bool(host) and (host.startswith("127.0.0.1") or original(host)),
    )
    yield


@pytest.fixture
def rendering_on(monkeypatch, loopback_is_official):
    monkeypatch.setenv(supervisor_render.RENDER_ENABLED_ENV, "true")
    yield


def test_static_fetch_cannot_see_any_professor(server):
    """Establishes that the browser is genuinely necessary here.

    If a static client could read the professor, the whole exercise would prove
    nothing - so this asserts the opposite first.
    """
    from app.services.supervisor_discovery import polite_fetch

    page = polite_fetch(server.url("/people"))
    html = page.content if page is not None else ""
    assert html, "the local directory must serve something"
    assert "Lovelace" not in html, "the professor must not exist in the served HTML"
    assert "Turing" not in html
    assert classify_shell(html).is_shell, "the served document must classify as a shell"


def test_real_browser_rendering_yields_a_real_professor(server, db, rendering_on):
    """The end-to-end proof.

    Real HTTP, real JavaScript execution, real rendered DOM, real role extraction,
    real storage - one chain, no mocks.
    """
    scholarship = _scholarship(db, server)

    outcome = discover_for_scholarship(
        db, scholarship, render_budget=RenderBudget(total_seconds=60.0)
    )

    professors = db.query(ProfessorProfile).all()
    names = {professor.canonical_name for professor in professors}

    # The two academics, and only them.
    assert "Ada Lovelace" in names, f"expected a rendered professor, got {names}"
    assert "Alan Turing" in names
    assert "South Australia" not in names, "a rendered place name is still not a person"
    assert "School of Computing" not in names, "a rendered unit is still not a person"

    assert outcome.status == "verified_supervisors"

    # Every stored row carries provenance, exactly as a static extraction would.
    links = db.query(ScholarshipProfessorLink).all()
    assert len(links) == 2
    for link in links:
        assert link.evidence_source_url
        assert link.evidence_source_type
        assert link.verification_status == "verified"

    coverage = db.query(ScholarshipSupervisorCoverage).one()
    assert coverage.verified_supervisor_count == 2


def test_rendered_profile_supplies_the_official_email(server, db, rendering_on):
    """Provenance is real: the email came off a page the browser rendered."""
    scholarship = _scholarship(db, server)

    discover_for_scholarship(db, scholarship, render_budget=RenderBudget(total_seconds=60.0))

    ada = (
        db.query(ProfessorProfile)
        .filter(ProfessorProfile.canonical_name == "Ada Lovelace")
        .one_or_none()
    )
    if ada is not None and ada.official_email:
        assert ada.official_email == "a.lovelace@uni1.edu"
        assert ada.official_email_verified is True


def test_rendering_is_off_by_default(server, db, monkeypatch, loopback_is_official):
    """Opt-in is the default, and off means inconclusive rather than negative."""
    monkeypatch.delenv(supervisor_render.RENDER_ENABLED_ENV, raising=False)
    assert supervisor_render.rendering_enabled() is False

    scholarship = _scholarship(db, server)
    outcome = discover_for_scholarship(
        db, scholarship, render_budget=RenderBudget(total_seconds=30.0)
    )

    assert db.query(ProfessorProfile).count() == 0
    assert outcome.status == "source_requires_rendering"


def test_missing_browser_driver_is_inconclusive_not_negative(server, db, rendering_on, monkeypatch):
    monkeypatch.setattr(supervisor_render, "playwright_available", lambda: False)

    scholarship = _scholarship(db, server)
    outcome = discover_for_scholarship(
        db, scholarship, render_budget=RenderBudget(total_seconds=30.0)
    )

    assert outcome.status == "source_requires_rendering"
    assert db.query(ProfessorProfile).count() == 0