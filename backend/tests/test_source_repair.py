"""Tests for official-source verification, repair, and safety invariants."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, ScholarshipVerificationHistory
from app.services.source_repair import (
    MIN_REPAIR_TITLE_OVERLAP,
    SourceQuality,
    SourceRepairService,
    _normalize_for_compare,
    _registrable,
    _sanitize_source_url,
    _title_overlap,
    iter_repair_candidates,
)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _record(session_factory, **overrides) -> int:
    defaults = dict(
        title="DAAD Study Scholarship",
        country="Germany",
        degree="Master",
        funding="Full",
        official_source="DAAD",
        official_source_url="https://www.daad.de/en/studying-in-germany/scholarships/",
        is_verified=True,
        verification_status="active",
    )
    defaults.update(overrides)
    s = session_factory()
    try:
        row = Scholarship(**defaults)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id
    finally:
        s.close()


class FakeResponse:
    def __init__(self, status_code=200, url="", text=""):
        self.status_code = status_code
        self.url = url
        self.text = text


class TestUrlHelpers:
    def test_normalize_ignores_scheme_www_and_trailing_slash(self):
        assert _normalize_for_compare("https://www.x.com/a/") == _normalize_for_compare("http://x.com/a")
        assert _normalize_for_compare("https://x.com/a/index.html") == _normalize_for_compare("https://x.com/a")

    def test_registrable_handles_multi_part_suffix(self):
        assert _registrable("www.studyinfinland.fi") == "studyinfinland.fi"
        assert _registrable("www.a.com.sg") == "a.com.sg"

    def test_title_overlap(self):
        assert _title_overlap("DAAD Study Scholarship Germany", "DAAD Study Scholarship") > 0.6
        assert _title_overlap("DAAD Study Scholarship", "Admissions Glossary") < MIN_REPAIR_TITLE_OVERLAP

    def test_sanitize_strips_session_id(self):
        out = _sanitize_source_url("https://x.go.kr/ko/main.do;jsessionid=ABC123")
        assert "jsessionid" not in out
        assert out.endswith("/ko/main.do")

    def test_sanitize_strips_tracking_and_fragment(self):
        out = _sanitize_source_url("https://x.com/a?utm_source=n&id=3#top")
        assert "utm_source" not in out
        assert "id=3" in out
        assert "#top" not in out

    def test_sanitize_leaves_clean_url_untouched(self):
        assert _sanitize_source_url("https://x.com/a/b") == "https://x.com/a/b"


class TestSourceVerification:
    def _service(self, session_factory, probe, dry_run=True):
        return SourceRepairService(session_factory, dry_run=dry_run)

    def test_live_unchanged_is_authoritative(self, session_factory):
        sid = _record(session_factory)

        def probe(self, url):
            return 200, url, None, None

        svc = self._service(session_factory, probe)
        with patch.object(SourceRepairService, "_probe", probe):
            result = svc.repair_one(sid)
        assert result.quality == SourceQuality.AUTHORITATIVE
        assert result.changed_url is False

    def test_redirect_is_recorded(self, session_factory):
        sid = _record(session_factory, official_source_url="https://www.daad.de/old-page")
        target = "https://www.daad.de/en/scholarships/current"

        def probe(self, url):
            if url == target:
                return 200, target, None, None
            return 200, target, None, None

        svc = self._service(session_factory, probe, dry_run=False)
        with patch.object(SourceRepairService, "_probe", probe):
            result = svc.repair_one(sid)

        assert result.quality == SourceQuality.REDIRECTED_TO_AUTHORITATIVE
        s = session_factory()
        try:
            assert s.get(Scholarship, sid).official_source_url == target
            history = s.scalars(
                select(ScholarshipVerificationHistory).where(
                    ScholarshipVerificationHistory.scholarship_id == sid
                )
            ).all()
            assert any(h.change_type == "redirected" for h in history)
        finally:
            s.close()

    def test_transient_failure_is_not_repaired(self, session_factory):
        sid = _record(session_factory)
        calls = []

        def probe(self, url):
            calls.append(url)
            return 403, url, "http_403", "HTTP 403"

        svc = self._service(session_factory, probe, dry_run=False)
        with patch.object(SourceRepairService, "_probe", probe):
            result = svc.repair_one(sid)

        assert result.quality == SourceQuality.UNAVAILABLE
        assert result.retryable is True
        s = session_factory()
        try:
            assert s.get(Scholarship, sid).official_source_url.startswith("https://www.daad.de/en/studying")
        finally:
            s.close()

    def test_aggregator_source_is_never_repaired(self, session_factory):
        sid = _record(
            session_factory,
            official_source_url="https://www.scholarshipdb.net/thing",
        )
        svc = self._service(session_factory, lambda self, u: (200, u, None, None))
        result = svc.repair_one(sid)
        assert result.quality == SourceQuality.UNRESOLVED
        assert "not an authoritative source" in result.reason

    def test_dead_url_without_evidence_stays_unresolved(self, session_factory):
        sid = _record(
            session_factory,
            title="Some Very Unusual Scholarship Name Here",
            official_source_url="https://www.daad.de/dead/page",
        )

        def probe(self, url):
            return 404, url, "http_404", "HTTP 404"

        svc = self._service(session_factory, probe, dry_run=False)
        with patch.object(SourceRepairService, "_probe", probe), patch.object(
            SourceRepairService, "_find_replacement", return_value=(None, "no evidence", 0.0)
        ):
            result = svc.repair_one(sid)

        assert result.quality == SourceQuality.UNRESOLVED
        s = session_factory()
        try:
            assert s.get(Scholarship, sid).official_source_url == "https://www.daad.de/dead/page"
        finally:
            s.close()

    def test_generic_candidate_is_rejected(self, session_factory):
        """A generic programme-path page with weak overlap must not be applied."""
        svc = SourceRepairService(session_factory, dry_run=True)
        resolved = type(
            "R",
            (),
            {
                "resolved_url": "https://www.example.org/studies",
                "page_title": "Admissions Glossary",
                "page_h1": None,
                "alternatives": [],
                "confidence": 0.95,
            },
        )()
        with patch.object(svc.resolver, "resolve_source", return_value=resolved):
            url, reason, overlap = svc._find_replacement(
                "https://www.example.org/dead", "DAAD Study Scholarship Programme"
            )
        assert url is None
        assert "sufficient title overlap" in reason

    def test_crash_does_not_escape(self, session_factory):
        sid = _record(session_factory)
        svc = SourceRepairService(session_factory, dry_run=True)
        with patch.object(SourceRepairService, "_probe", side_effect=RuntimeError("boom")):
            result = svc.repair_one(sid)
        assert result.quality == SourceQuality.UNRESOLVED
        assert "RuntimeError" in (result.error or "")


class TestResumability:
    def test_candidate_ids_are_deterministic_and_resumable(self, session_factory):
        ids = []
        for i in range(5):
            ids.append(_record(session_factory, title=f"S{i}", official_source_url=f"https://www.daad.de/p{i}"))
        ids.sort()

        s = session_factory()
        try:
            first = iter_repair_candidates(s)
            after_first_two = iter_repair_candidates(s, start_after=ids[1])
            rest = iter_repair_candidates(s, start_after=ids[1])
        finally:
            s.close()

        assert first == ids
        assert after_first_two == ids[2:]
        # Resuming twice yields the same window (idempotent selection).
        assert rest == after_first_two

    def test_records_without_source_url_are_excluded(self, session_factory):
        _record(session_factory, official_source_url="https://www.daad.de/a")
        _record(session_factory, title="no src", official_source_url=None)
        s = session_factory()
        try:
            assert len(iter_repair_candidates(s)) == 1
        finally:
            s.close()

    def test_explicit_ids_filter(self, session_factory):
        a = _record(session_factory, title="A", official_source_url="https://www.daad.de/a")
        b = _record(session_factory, title="B", official_source_url="https://www.daad.de/b")
        s = session_factory()
        try:
            assert iter_repair_candidates(s, ids=[b]) == [b]
            assert iter_repair_candidates(s, ids=[]) == []
        finally:
            s.close()


class TestEvidenceIdempotency:
    def test_second_identical_run_creates_no_new_write(self, session_factory):
        sid = _record(session_factory, official_source_url="https://www.daad.de/old")
        target = "https://www.daad.de/en/new"

        def probe(self, url):
            return 200, target, None, None

        svc = SourceRepairService(session_factory, dry_run=False)
        with patch.object(SourceRepairService, "_probe", probe):
            svc.repair_one(sid)

        s = session_factory()
        try:
            first_count = len(
                s.scalars(
                    select(ScholarshipVerificationHistory).where(
                        ScholarshipVerificationHistory.scholarship_id == sid
                    )
                ).all()
            )
        finally:
            s.close()

        # Second run: the stored URL is already the final URL, so nothing changes.
        with patch.object(SourceRepairService, "_probe", probe):
            second = svc.repair_one(sid)

        s = session_factory()
        try:
            second_count = len(
                s.scalars(
                    select(ScholarshipVerificationHistory).where(
                        ScholarshipVerificationHistory.scholarship_id == sid
                    )
                ).all()
            )
        finally:
            s.close()

        assert second.quality == SourceQuality.AUTHORITATIVE
        assert second.changed_url is False
        # Only the two verification-log rows exist; no new redirect was written.
        assert second_count == first_count
