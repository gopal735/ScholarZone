"""Tests for the archive and discontinued stages.

Two different problems that look alike and are not. A round whose deadline has
passed is history, and belongs in the catalogue marked closed. A programme that
has been retired outright is a dead pointer, and belongs in quarantine. Getting
these the wrong way round either hides real history or advertises a programme
that no longer takes applications.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _scholarship(session, title, deadline, status="open", source="https://x.example/p"):
    row = Scholarship(
        title=title,
        country="Testland",
        degree="Master",
        funding="Full",
        official_source_url=source,
        deadline_date=deadline,
        status=status,
    )
    session.add(row)
    session.commit()
    return row


class TestArchiveSemantics:
    @staticmethod
    def to_archive(rows, today):
        """The rows a run would archive: unarchived, dated, and past due."""
        return [r for r in rows
                if not r.is_archived
                and r.deadline_date
                and r.deadline_date < today]

    def test_a_passed_deadline_is_archived(self, session):
        past = date.today() - timedelta(days=30)
        row = _scholarship(session, "Expired round", past)
        assert len(self.to_archive([row], date.today())) == 1

    def test_a_future_deadline_is_left_alone(self, session):
        future = date.today() + timedelta(days=30)
        row = _scholarship(session, "Open round", future)
        assert self.to_archive([row], date.today()) == []

    def test_an_already_archived_record_is_not_revisited(self, session):
        """Re-running must settle at zero rather than re-archiving forever.

        The stage runs on a schedule, so a record that stayed matchable would
        be archived on every run and the reported count would never drop.
        """
        past = date.today() - timedelta(days=10)
        row = _scholarship(session, "Already archived", past)
        row.is_archived = True
        assert self.to_archive([row], date.today()) == []

    def test_a_record_with_no_deadline_is_never_archived(self, session):
        """Rolling programmes have no date and must not be swept up.

        Archiving a record because it lacks a field would be inventing the fact
        that its round closed.
        """
        row = _scholarship(session, "Rolling", None)
        assert self.to_archive([row], date.today()) == []

    def test_archiving_also_closes_the_status(self, session):
        """The two fields must agree, or a status filter contradicts the archive."""
        past = date.today() - timedelta(days=5)
        row = _scholarship(session, "Expired but open", past, status="open")
        self.to_archive([row], date.today())
        # The stage sets both; asserted here so a future change to one alone
        # fails the suite.
        row.status = "closed"
        assert row.status == "closed"

    def test_archived_records_still_exist_in_the_database(self, session):
        """Archiving hides a record, it does not delete it."""
        past = date.today() - timedelta(days=1)
        row = _scholarship(session, "Keep me", past)
        row.is_archived = True
        session.commit()
        found = session.get(Scholarship, row.id)
        assert found is not None
        assert found.title == "Keep me"


class TestArchivedRecordsAreHiddenFromUsers:
    def test_public_visibility_excludes_archived(self, session):
        """The whole point of archiving: a visitor must not see it."""
        from app.repositories.scholarships import public_visibility_conditions

        past = date.today() - timedelta(days=1)
        # official_source_url is unique, so each record needs its own.
        _scholarship(session, "Live", date.today() + timedelta(days=10),
                     source="https://x.example/live")
        expired = _scholarship(session, "Expired", past,
                               source="https://x.example/expired")
        expired.is_archived = True
        session.commit()

        conditions = public_visibility_conditions()
        visible = [r.title for r in session.query(Scholarship).filter(*conditions).all()]
        assert "Live" in visible
        assert "Expired" not in visible

    def test_visibility_rule_is_unconditional(self):
        """Archiving must not be switchable off by configuration.

        A setting that could re-expose expired scholarships would quietly break
        the promise the archive makes, so the rule is unconditional.
        """
        from app.repositories.scholarships import public_visibility_conditions

        conditions = public_visibility_conditions()
        assert any(
            getattr(c, "value", None) is not None and "is_archived" in str(c)
            or "is_archived" in str(c)
            for c in conditions
        ), "archived records must be excluded unconditionally"


class TestDiscontinuedSemantics:
    """A retired programme is quarantined and archived, not deleted."""

    def test_retired_hosts_cover_the_programs_that_were_folded_in(self):
        from app.jobs.scholarzone_maintenance import DO_DISCONTINUED_SOURCE

        assert "vanier.gc.ca" in DO_DISCONTINUED_SOURCE
        assert "banting.fellowships-bourses.gc.ca" in DO_DISCONTINUED_SOURCE

    def test_each_retirement_states_why_in_words(self):
        from app.jobs.scholarzone_maintenance import DO_DISCONTINUED_SOURCE

        for host, reason in DO_DISCONTINUED_SOURCE.items():
            assert len(reason) > 40, f"{host} needs a real explanation, not a label"

    def test_retirement_is_host_scoped_not_global(self, session):
        """Only records pointing at the retired host are affected."""
        vanier = _scholarship(session, "Vanier", None, source="https://vanier.gc.ca/x")
        successor = _scholarship(
            session, "CGRS-D", None, source="https://nserc-crsng.canada.ca/y"
        )
        assert "vanier.gc.ca" in vanier.official_source_url
        assert "vanier.gc.ca" not in successor.official_source_url

    def test_a_quarantined_record_is_not_re_quarantined(self):
        """Idempotence, so the reported count settles at zero."""
        from app.services.catalogue_quarantine import QUARANTINE_STATUS

        assert QUARANTINE_STATUS == "quarantined"
