"""Tests for scholarship lifecycle and semantic identity intelligence."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.lifecycle_identity import (
    APPLICATION_OPEN,
    ARCHIVED,
    CLOSED,
    DEADLINE_NEAR,
    DISCOVERED,
    IDENTITY_CANONICAL,
    IDENTITY_EXACT,
    IDENTITY_NEW,
    IDENTITY_PROVIDER,
    IDENTITY_REVIEW,
    IDENTITY_SIMILAR,
    RESULT_PENDING,
    UNKNOWN,
    CYCLE_DISTINCT,
    CYCLE_NEW,
    CYCLE_RENAMED,
    CYCLE_SAME,
    IdentityFingerprint,
    IdentityResolution,
    LifecycleState,
    LifecycleTransition,
    _extract_year_hint,
    _normalize_degree,
    _normalize_funding,
    batch_classify_lifecycle,
    batch_resolve_identities,
    build_fingerprint,
    classify_lifecycle_state,
    compute_lifecycle_transition,
    get_lifecycle_timestamp_fields,
    get_related_scholarships,
    is_same_program,
    resolve_cycle_status,
    resolve_identity,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


_url_counter = 0


@pytest.fixture
def scholarship_factory(session):
    def _make(**kwargs):
        global _url_counter
        _url_counter += 1
        defaults = {
            "title": "Test Scholarship",
            "country": "Germany",
            "degree": "Masters",
            "funding": "Full",
            "official_source_url": f"https://example.com/scholarship-{_url_counter}",
            "official_source": "Test Provider",
        }
        defaults.update(kwargs)
        s = Scholarship(**defaults)
        session.add(s)
        session.commit()
        return s
    return _make


class TestBuildFingerprint:
    def test_basic_fingerprint(self):
        fp = build_fingerprint(
            title="DAAD Scholarship 2026",
            provider="DAAD",
            official_source_url="https://daad.de/scholarship/123",
            degree="Masters",
            funding="Full",
            country="Germany",
        )
        assert fp.provider == "daad"
        assert fp.domain == "daad.de"
        assert "daad" in fp.title
        assert fp.degree == "masters"
        assert fp.funding == "full"
        assert fp.country == "germany"
        assert fp.year_hint == 2026

    def test_empty_fields(self):
        fp = build_fingerprint(None, None, None, None, None, None)
        assert fp.provider == ""
        assert fp.domain == ""
        assert fp.title == ""
        assert fp.degree == ""
        assert fp.funding == ""
        assert fp.country == ""
        assert fp.year_hint is None

    def test_url_path_extraction(self):
        fp = build_fingerprint(
            title="Test",
            provider="Provider",
            official_source_url="https://example.com/path/to/scholarship",
            degree="Bachelors",
            funding="Partial",
            country="France",
        )
        assert fp.url_path == "/path/to/scholarship"

    def test_degree_normalization(self):
        assert _normalize_degree("PhD") == "phd"
        assert _normalize_degree("Ph.D") == "phd"
        assert _normalize_degree("Masters") == "masters"
        assert _normalize_degree("MS") == "masters"
        assert _normalize_degree("Bachelors") == "bachelors"
        assert _normalize_degree("BS") == "bachelors"
        assert _normalize_degree("PostDoc") == "postdoc"

    def test_funding_normalization(self):
        assert _normalize_funding("Full") == "full"
        assert _normalize_funding("Fully Funded") == "full"
        assert _normalize_funding("Partial") == "partial"
        assert _normalize_funding("Tuition Waiver") == "tuition"

    def test_year_hint_extraction(self):
        assert _extract_year_hint("Scholarship 2026") == 2026
        assert _extract_year_hint("Program 2025-2026") == 2026
        assert _extract_year_hint("No year here") is None
        assert _extract_year_hint(None) is None


class TestExactIdentity:
    def test_exact_url_match(self, session, scholarship_factory):
        existing = scholarship_factory(
            official_source_url="https://daad.de/scholarship/123",
        )

        resolution = resolve_identity(
            session=session,
            title="DAAD Scholarship",
            provider="DAAD",
            official_source_url="https://daad.de/scholarship/123",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert resolution.resolution_type == IDENTITY_EXACT
        assert resolution.matched_id == existing.id
        assert resolution.confidence == 1.0

    def test_exact_url_match_with_trailing_slash(self, session, scholarship_factory):
        existing = scholarship_factory(
            official_source_url="https://daad.de/scholarship/123",
        )

        resolution = resolve_identity(
            session=session,
            title="DAAD Scholarship",
            provider="DAAD",
            official_source_url="https://daad.de/scholarship/123/",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert resolution.resolution_type == IDENTITY_EXACT
        assert resolution.matched_id == existing.id


class TestCanonicalIdentity:
    def test_canonical_domain_path_match(self, session, scholarship_factory):
        existing = scholarship_factory(
            official_source_url="https://daad.de/scholarship/123",
            catalogue_url="https://daad.de/catalogue",
        )

        resolution = resolve_identity(
            session=session,
            title="Different Title",
            provider="Different Provider",
            official_source_url="https://daad.de/scholarship/123",
            degree="PhD",
            funding="Partial",
            country="Germany",
        )

        assert resolution.resolution_type in (IDENTITY_EXACT, IDENTITY_CANONICAL)
        assert resolution.matched_id == existing.id


class TestProviderIdentity:
    def test_provider_metadata_match(self, session, scholarship_factory):
        existing = scholarship_factory(
            official_source="DAAD",
            official_source_url="https://daad.de/scholarship/123",
            title="DAAD Masters Scholarship 2025",
            country="Germany",
            degree="Masters",
            funding="Full",
        )

        resolution = resolve_identity(
            session=session,
            title="DAAD Masters Scholarship 2026",
            provider="DAAD",
            official_source_url="https://daad.de/scholarship/456",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert resolution.resolution_type in (IDENTITY_PROVIDER, IDENTITY_SIMILAR)
        assert resolution.matched_id == existing.id


class TestRenamedScholarship:
    def test_renamed_same_provider(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Erasmus Mundus Scholarship 2025",
            official_source_url="https://erasmus.europa.eu/scholarship/123",
            official_source="Erasmus",
            country="EU (multiple)",
            degree="Masters",
            funding="Full",
        )

        resolution = resolve_identity(
            session=session,
            title="Erasmus+ Masters Fellowship 2026",
            provider="Erasmus",
            official_source_url="https://erasmus.europa.eu/scholarship/123",
            degree="Masters",
            funding="Full",
            country="EU (multiple)",
        )

        assert resolution.matched_id == existing.id

    def test_resolve_cycle_status_renamed(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="DAAD Helmut Schmidt Scholarship Program",
            official_source_url="https://provider-test.com/program/123",
            official_source="DAAD",
            country="Germany",
            degree="Masters",
            funding="Full",
        )

        fingerprint = build_fingerprint(
            title="DAAD Helmut Schmidt Scholarship Programme",
            provider="DAAD",
            official_source_url="https://provider-test.com/program/123",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        resolution = IdentityResolution(
            resolution_type=IDENTITY_EXACT,
            matched_id=existing.id,
            confidence=1.0,
            fingerprint=fingerprint,
            reason="exact_match",
        )

        cycle_resolution = resolve_cycle_status(session, resolution, "DAAD Helmut Schmidt Scholarship Programme")
        assert cycle_resolution.cycle_status == CYCLE_RENAMED


class TestAnnualCycleDetection:
    def test_new_cycle_same_program(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="DAAD Scholarship 2025",
            official_source_url="https://daad.de/scholarship/annual",
            official_source="DAAD",
            country="Germany",
            degree="Masters",
            funding="Full",
        )

        fingerprint = build_fingerprint(
            title="DAAD Scholarship 2026",
            provider="DAAD",
            official_source_url="https://daad.de/scholarship/annual",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        resolution = IdentityResolution(
            resolution_type=IDENTITY_CANONICAL,
            matched_id=existing.id,
            confidence=0.95,
            fingerprint=fingerprint,
            reason="canonical_match",
        )

        cycle_resolution = resolve_cycle_status(session, resolution, "DAAD Scholarship 2026")
        assert cycle_resolution.cycle_status == CYCLE_NEW


class TestDistinctRelatedPrograms:
    def test_different_programs_same_provider(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="Engineering Scholarship",
            official_source_url="https://provider-distinct.com/engineering",
            official_source="Provider",
            country="Germany",
            degree="Masters",
            funding="Full",
        )

        fingerprint = build_fingerprint(
            title="Medical Research Fellowship",
            provider="Provider",
            official_source_url="https://provider-distinct.com/medical",
            degree="PhD",
            funding="Partial",
            country="Germany",
        )

        resolution = IdentityResolution(
            resolution_type=IDENTITY_SIMILAR,
            matched_id=existing.id,
            confidence=0.5,
            fingerprint=fingerprint,
            reason="similarity_match",
        )

        cycle_resolution = resolve_cycle_status(session, resolution, "Medical Research Fellowship")
        assert cycle_resolution.cycle_status == CYCLE_DISTINCT


class TestGenuineNewScholarship:
    def test_new_scholarship(self, session):
        resolution = resolve_identity(
            session=session,
            title="Brand New Scholarship",
            provider="New Provider",
            official_source_url="https://new.com/scholarship",
            degree="Masters",
            funding="Full",
            country="Japan",
        )

        assert resolution.resolution_type == IDENTITY_NEW
        assert resolution.matched_id is None
        assert resolution.confidence == 0.0


class TestAmbiguousIdentityReview:
    def test_ambiguous_goes_to_review(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="German Academic Exchange 2025",
            official_source_url="https://exchange.de/program/1",
            official_source="Exchange",
            country="Germany",
            degree="Masters",
            funding="Full",
        )

        resolution = resolve_identity(
            session=session,
            title="German Research Fellowship",
            provider="Exchange",
            official_source_url="https://exchange.de/program/2",
            degree="PhD",
            funding="Partial",
            country="Germany",
        )

        assert resolution.resolution_type in (IDENTITY_SIMILAR, IDENTITY_REVIEW, IDENTITY_PROVIDER)


class TestLifecycleDiscovered:
    def test_discovered_unverified(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=False,
            verification_status="pending",
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == DISCOVERED
        assert "verification_pending" in state.reason

    def test_discovered_pending_status(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=False,
            verification_status="pending",
            deadline_date=date(2026, 12, 31),
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == DISCOVERED


class TestLifecycleApplicationOpen:
    def test_application_open_with_future_deadline(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2026, 12, 31),
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == APPLICATION_OPEN

    def test_application_open_active_status(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="active",
            deadline_date=date(2027, 3, 1),
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == APPLICATION_OPEN


class TestLifecycleDeadlineNear:
    def test_deadline_near(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2026, 9, 15),
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == DEADLINE_NEAR
        assert "deadline_within_30d" in state.reason


class TestLifecycleClosed:
    def test_closed_deadline_passed(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2026, 8, 15),
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == CLOSED
        assert "deadline_passed" in state.reason

    def test_closed_status(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="closed",
            deadline_date=date(2027, 1, 1),
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == CLOSED


class TestLifecycleArchived:
    def test_archived_status(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="archived",
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == ARCHIVED

    def test_archived_deadline_long_past(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2024, 1, 1),
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == ARCHIVED


class TestLifecycleResultPending:
    def test_result_pending_status(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="result_pending",
            deadline_date=date(2026, 10, 1),
            official_source_url="https://result-pending-test.com/scholarship",
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == RESULT_PENDING


class TestLifecycleUnknown:
    def test_unknown_insufficient_data(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="",
            deadline_date=None,
        )

        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.state == UNKNOWN


class TestLifecycleTransitions:
    def test_transition_detected(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2026, 9, 15),
        )

        transition = compute_lifecycle_transition(
            session, s, APPLICATION_OPEN, date(2026, 9, 1)
        )
        assert transition is not None
        assert transition.from_state == APPLICATION_OPEN
        assert transition.to_state == DEADLINE_NEAR

    def test_no_transition_same_state(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2027, 1, 1),
        )

        transition = compute_lifecycle_transition(
            session, s, APPLICATION_OPEN, date(2026, 9, 1)
        )
        assert transition is None

    def test_terminal_state_no_transition(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="archived",
        )

        transition = compute_lifecycle_transition(
            session, s, ARCHIVED, date(2026, 9, 1)
        )
        assert transition is None


class TestIdempotency:
    def test_resolve_identity_idempotent(self, session, scholarship_factory):
        existing = scholarship_factory(
            official_source_url="https://test.com/scholarship",
        )

        r1 = resolve_identity(
            session=session,
            title="Test Scholarship",
            provider="Test",
            official_source_url="https://test.com/scholarship",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        r2 = resolve_identity(
            session=session,
            title="Test Scholarship",
            provider="Test",
            official_source_url="https://test.com/scholarship",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert r1.resolution_type == r2.resolution_type
        assert r1.matched_id == r2.matched_id
        assert r1.confidence == r2.confidence

    def test_classify_lifecycle_idempotent(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2027, 1, 1),
        )

        state1 = classify_lifecycle_state(session, s, date(2026, 9, 1))
        state2 = classify_lifecycle_state(session, s, date(2026, 9, 1))

        assert state1.state == state2.state
        assert state1.reason == state2.reason


class TestDuplicatePrevention:
    def test_same_url_not_duplicated(self, session, scholarship_factory):
        existing = scholarship_factory(
            official_source_url="https://test.com/scholarship",
        )

        resolution = resolve_identity(
            session=session,
            title="Same Scholarship",
            provider="Test",
            official_source_url="https://test.com/scholarship",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert resolution.matched_id == existing.id
        assert resolution.resolution_type == IDENTITY_EXACT

    def test_same_provider_same_title_not_duplicated(self, session, scholarship_factory):
        existing = scholarship_factory(
            title="DAAD Masters",
            official_source="DAAD",
            official_source_url="https://daad.de/program/1",
            country="Germany",
            degree="Masters",
            funding="Full",
        )

        resolution = resolve_identity(
            session=session,
            title="DAAD Masters",
            provider="DAAD",
            official_source_url="https://daad.de/program/2",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert resolution.matched_id is not None


class TestIsSameProgram:
    def test_same_program_by_domain_and_path(self, session, scholarship_factory):
        s1 = scholarship_factory(
            official_source_url="https://test-same.com/scholarship/123",
            title="Test Scholarship Program",
            official_source="Test Provider",
        )
        s2 = scholarship_factory(
            official_source_url="https://test-same.com/scholarship/456",
            title="Test Scholarship Program 2026",
            official_source="Test Provider",
        )

        assert is_same_program(session, s1.id, s2.id)

    def test_different_programs(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="Program A",
            official_source="Provider A",
            official_source_url="https://a.com/program",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        s2 = scholarship_factory(
            title="Program B",
            official_source="Provider B",
            official_source_url="https://b.com/program",
            country="France",
            degree="PhD",
            funding="Partial",
        )

        assert not is_same_program(session, s1.id, s2.id)


class TestGetRelatedScholarships:
    def test_related_by_provider(self, session, scholarship_factory):
        s1 = scholarship_factory(
            title="Program A",
            official_source="DAAD",
            official_source_url="https://daad.de/program/a",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        s2 = scholarship_factory(
            title="Program B",
            official_source="DAAD",
            official_source_url="https://daad.de/program/b",
            country="Germany",
            degree="Masters",
            funding="Full",
        )
        s3 = scholarship_factory(
            title="Unrelated Program",
            official_source="Other",
            official_source_url="https://other.com/program",
            country="France",
            degree="PhD",
            funding="Partial",
        )

        related = get_related_scholarships(session, s1.id)
        assert s2.id in related
        assert s3.id not in related


class TestBatchOperations:
    def test_batch_resolve_identities(self, session, scholarship_factory):
        scholarship_factory(
            title="Program A",
            official_source="DAAD",
            official_source_url="https://daad.de/program/a",
            country="Germany",
            degree="Masters",
            funding="Full",
        )

        candidates = [
            {
                "title": "Program A",
                "provider": "DAAD",
                "official_source_url": "https://daad.de/program/a",
                "degree": "Masters",
                "funding": "Full",
                "country": "Germany",
            },
            {
                "title": "New Program",
                "provider": "New",
                "official_source_url": "https://new.com/program",
                "degree": "PhD",
                "funding": "Partial",
                "country": "Japan",
            },
        ]

        results = batch_resolve_identities(session, candidates)
        assert len(results) == 2
        assert results[0].resolution_type == IDENTITY_EXACT
        assert results[1].resolution_type == IDENTITY_NEW

    def test_batch_classify_lifecycle(self, session, scholarship_factory):
        s1 = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2027, 1, 1),
        )
        s2 = scholarship_factory(
            is_verified=False,
            verification_status="pending",
        )

        states = batch_classify_lifecycle(session, [s1, s2], date(2026, 9, 1))
        assert len(states) == 2
        assert states[0].state == APPLICATION_OPEN
        assert states[1].state == DISCOVERED


class TestDeterministicResults:
    def test_fingerprint_deterministic(self):
        fp1 = build_fingerprint(
            title="Test Scholarship 2026",
            provider="Test",
            official_source_url="https://test.com/scholarship",
            degree="Masters",
            funding="Full",
            country="Germany",
        )
        fp2 = build_fingerprint(
            title="Test Scholarship 2026",
            provider="Test",
            official_source_url="https://test.com/scholarship",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert fp1 == fp2

    def test_lifecycle_state_deterministic(self, session, scholarship_factory):
        s = scholarship_factory(
            is_verified=True,
            status="open",
            deadline_date=date(2027, 1, 1),
        )

        for _ in range(5):
            state = classify_lifecycle_state(session, s, date(2026, 9, 1))
            assert state.state == APPLICATION_OPEN


class TestGetLifecycleTimestampFields:
    def test_timestamp_fields(self, session, scholarship_factory):
        s = scholarship_factory()

        fields = get_lifecycle_timestamp_fields(s)
        assert "created_at" in fields
        assert "updated_at" in fields
        assert "last_verified_at" in fields
        assert "last_verified_date" in fields
        assert "next_verification_due" in fields


class TestSchedulerCompatibility:
    def test_lifecycle_state_has_scholarship_id(self, session, scholarship_factory):
        s = scholarship_factory()
        state = classify_lifecycle_state(session, s, date(2026, 9, 1))
        assert state.scholarship_id == s.id

    def test_identity_resolution_has_matched_id(self, session, scholarship_factory):
        existing = scholarship_factory(
            official_source_url="https://test.com/scholarship",
        )

        resolution = resolve_identity(
            session=session,
            title="Test",
            provider="Test",
            official_source_url="https://test.com/scholarship",
            degree="Masters",
            funding="Full",
            country="Germany",
        )

        assert resolution.matched_id == existing.id
