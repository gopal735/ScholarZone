"""The verified-only catalogue switch, and what it must not do by default.

``SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED`` exists in configuration but was never
wired to the canonical visibility predicate, so turning it on did nothing. It
is wired here, and the default stays OFF: a scholarship that has not been
re-checked is not a wrong scholarship, and a flag that hid 91 records without
a redeploy decision would be a trap rather than a feature.

These tests pin both halves: the default is unchanged, and the flag — when the
owner turns it on — hides an unverified record while leaving the security and
lifecycle exclusions exactly as they were.
"""
from __future__ import annotations

from datetime import datetime, timezone

import inspect
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.repositories.scholarships import public_visibility_conditions

IMG = "https://example.org/photo.jpg"
WHEN = datetime(2026, 1, 1, tzinfo=timezone.utc)

_seq = iter(range(1, 10_000))


@pytest.fixture()
def engine_factory(monkeypatch):
    """A settings stub whose ``public_require_verified`` a test controls."""
    from app.core.config import get_settings

    real = get_settings()

    class _Settings:
        public_require_verified = False
        public_require_verified_image = False
        public_allow_third_party_image = False

        def __getattr__(self, name):
            return getattr(real, name)

    settings = _Settings()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine, settings


def _visible(engine) -> set[int]:
    session = sessionmaker(bind=engine)()
    try:
        return set(
            session.scalars(
                select(Scholarship.id).where(*public_visibility_conditions())
            ).all()
        )
    finally:
        session.close()


def _row(engine, **kwargs) -> int:
    kwargs.setdefault("official_source_url", f"https://example.org/case-{next(_seq)}")
    row = Scholarship(
        title=kwargs.pop("title", "T"),
        country=kwargs.pop("country", "GB"),
        degree=kwargs.pop("degree", "masters"),
        funding=kwargs.pop("funding", "full"),
        is_archived=kwargs.pop("is_archived", False),
        verification_status=kwargs.pop("verification_status", "active"),
        is_verified=kwargs.pop("is_verified", True),
        image_url=kwargs.pop("image_url", IMG),
        image_verified_at=kwargs.pop("image_verified_at", None),
        image_source_type=kwargs.pop("image_source_type", "issuer_logo"),
        **kwargs,
    )
    session = sessionmaker(bind=engine)()
    session.add(row)
    session.commit()
    session.refresh(row)
    sid = row.id
    session.close()
    return sid


# ── the default is untouched ────────────────────────────────────────────


def test_unverified_record_stays_visible_by_default(engine_factory):
    """The default must not change: trust labelling, not visibility."""
    engine, _ = engine_factory
    unverified = _row(engine, verification_status="needs_review")
    assert unverified in _visible(engine)


def test_default_does_not_add_a_verification_condition(engine_factory):
    engine, settings = engine_factory
    _row(engine, verification_status="needs_review")
    conditions = public_visibility_conditions()
    assert settings.public_require_verified is False
    # The predicate stays the three documented exclusions.
    assert len(conditions) == 3
    # And they are SQL expressions, not a Python-side filter that the
    # directory's count query would quietly bypass.
    assert all(hasattr(c, "compile") for c in conditions)


# ── the switch, when the owner turns it on ──────────────────────────────


def test_verified_only_hides_unverified_but_keeps_verified(engine_factory):
    engine, settings = engine_factory
    active = _row(engine, verification_status="active")
    needs_review = _row(engine, verification_status="needs_review")
    unverified = _row(engine, verification_status="unverified")

    settings.public_require_verified = True

    visible = _visible(engine)
    assert active in visible
    assert needs_review not in visible
    assert unverified not in visible


def test_verified_only_keeps_the_security_and_lifecycle_exclusions(engine_factory):
    """The flag is a trust gate, not a replacement for the other exclusions."""
    engine, settings = engine_factory
    open_active = _row(engine, verification_status="active")
    quarantined = _row(engine, verification_status="active")
    archived = _row(engine, verification_status="active")
    closed = _row(engine, verification_status="active")

    session = sessionmaker(bind=engine)()
    session.query(Scholarship).filter(Scholarship.id == quarantined).update(
        {"verification_status": "quarantined"}
    )
    session.query(Scholarship).filter(Scholarship.id == archived).update(
        {"is_archived": True}
    )
    session.query(Scholarship).filter(Scholarship.id == closed).update(
        {"status": "closed"}
    )
    session.commit()
    session.close()

    settings.public_require_verified = True

    visible = _visible(engine)
    assert open_active in visible
    assert quarantined not in visible
    assert archived not in visible
    assert closed not in visible


def test_verified_only_condition_is_part_of_the_query_not_a_python_filter(engine_factory):
    """A count that bypasses the predicate would advertise a different total."""
    engine, settings = engine_factory
    settings.public_require_verified = True
    conditions = public_visibility_conditions()
    assert len(conditions) == 4
    assert all(hasattr(c, "compile") for c in conditions)


def test_the_gate_uses_the_verification_contract_constant():
    """The flag must not define "verified" itself.

    A literal here would outlive a change to the contract, and the gate would
    quietly filter on a status whose meaning the rest of the app no longer
    shares.
    """
    import app.repositories.scholarships as repository
    from app.verification_contract import AUTHORITATIVE_VERIFIED_STATUS

    conditions_source = inspect.getsource(repository.public_visibility_conditions)
    assert "AUTHORITATIVE_VERIFIED_STATUS" in conditions_source
    assert '"active"' not in conditions_source
    assert AUTHORITATIVE_VERIFIED_STATUS == "active"


def test_the_setting_is_read_on_every_call_not_captured_at_import():
    """A copy taken at import would make the environment switch inert."""
    import app.core.config as config_module
    import app.repositories.scholarships as repository

    calls = []

    class _Recording:
        public_require_verified = False

        def __getattr__(self, name):
            raise AttributeError(name)

    def recording_get_settings():
        calls.append(1)
        return _Recording()

    original = config_module.get_settings
    config_module.get_settings = recording_get_settings
    try:
        public_visibility_conditions()
        # Swapping the callable is enough to change the outcome, which is only
        # true if the predicate calls through the module each time.
        _Recording.public_require_verified = True
        len(public_visibility_conditions())
    finally:
        config_module.get_settings = original
        _Recording.public_require_verified = False

    assert len(calls) == 2
    assert repository.config is config_module
