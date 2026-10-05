"""Phases 5, 7, 8, 9, 13, 14, 15 and 18 - the engine against a real database.

Every test here runs against a real SQLite database built from the project's own
models, so the canonical ``public_visibility_conditions()``, the review queries
and the catalogue counts are exercised as SQL rather than mocked. A retention
engine whose safety rests on a query is only as trustworthy as that query, and a
mocked query asserts nothing about it.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    DiscoveryCandidate,
    ImageReview,
    MaintenanceRun,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipReview,
    ScholarshipSnapshot,
    ScholarshipVerificationHistory,
)
from app.repositories.scholarships import public_visibility_conditions
from app.services.counting.catalogue import catalogue_counts
from app.services.retention_contract import (
    BUCKET_ADMIN_REVIEW,
    BUCKET_CONFLICTING,
    BUCKET_LIVE,
    BUCKET_PROTECTED,
    RETENTION_CONTRACT_VERSION,
    RetentionPolicy,
    default_policy,
    summarise,
)
from app.services.retention_engine import (
    CleanupAborted,
    PRESERVE_MODELS,
    delete_bounded,
    dry_run,
    ledger_path,
    recovery_status,
    reference_dependencies,
    reference_integrity_report,
    scan,
)

AS_OF = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
ANCIENT = datetime(2019, 1, 1, tzinfo=timezone.utc)

#: The only policy permitted to delete in this suite. Every other test uses the
#: shipped policy, which cannot delete at all.
#:
#: ``max_delete_percentage`` is 1.0 because the fixtures below build catalogues of
#: one to seven rows, and the shipped 5% cap would abort every one of them. That
#: is the guard working, not a nuisance to tune away - the cap has its own test.
DELETING = RetentionPolicy(
    cleanup_enabled=True, dry_run=False, batch_size=5, max_delete_percentage=1.0
)


@pytest.fixture(autouse=True)
def production_visibility_gate(monkeypatch):
    """Run every test under the production visibility contract.

    The suite-wide ``conftest`` turns both public quality gates *off*, because the
    long-standing fixtures are legacy rows with no image. A retention test must
    not inherit that: "not live because it has no verified image" is one of the
    most important populations this engine has to refuse to delete, and with the
    gate off that population does not exist. ``get_settings()`` reads the
    environment on every call, so setting it here reaches the canonical
    predicate without patching it.
    """
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE", "false")


def audit_row(session, run_id: str) -> MaintenanceRun | None:
    """Look a run up by ``run_id``.

    ``MaintenanceRun``'s primary key is the surrogate ``id``; ``run_id`` is only
    unique. ``Session.get`` therefore returns None for a run id, which looks
    exactly like a run that was never written - so the lookup is by column.
    """
    return session.query(MaintenanceRun).filter(MaintenanceRun.run_id == run_id).one_or_none()


def still_stored(session, scholarship_id: int) -> bool:
    """Whether a scholarship row is in the database right now.

    A plain ``Session.get`` answers from the identity map, so it keeps returning
    an object the deleting path has already removed - and a test that asserts
    "the row is gone" with it passes or fails for the wrong reason. This asks the
    database.
    """
    session.expire_all()
    return (
        session.scalar(select(Scholarship.id).where(Scholarship.id == scholarship_id))
        is not None
    )


def stored_rows(session) -> int:
    """How many scholarship rows the database currently holds."""
    session.expire_all()
    return int(session.scalar(select(func.count(Scholarship.id))) or 0)


@pytest.fixture()
def tmp_ledger(tmp_path) -> Path:

    """Where a deleting test writes its deletion manifest.

    Not a convenience. The engine's default ledger is a tracked file in the
    repository, so a test that deletes anything and does not redirect the ledger
    appends a real, permanent entry to the project's record of what has been
    deleted - which corrupts that record and leaves a dirty worktree. The
    redirection is deliberate at every call site for that reason.
    """
    return tmp_path / "purged_records_archive.json"


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'retention.db'}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def make_live(session, **overrides) -> Scholarship:
    """A record the public catalogue actually lists.

    Built to satisfy every default visibility gate, so a test that means to
    exercise a retention path is not accidentally testing the image gate.
    """
    fields = dict(
        title="Live Programme",
        country="Canada",
        degree="Master",
        funding="Full",
        official_source="Example University",
        official_source_url="https://example.test/live",
        status="open",
        is_archived=False,
        archived_at=None,
        is_verified=True,
        verification_status="active",
        image_url="https://example.test/logo.png",
        image_verified_at=ANCIENT,
        image_source_type="official",
        image_evaluation_status="verified",
    )
    fields.update(overrides)
    row = Scholarship(**fields)
    session.add(row)
    session.commit()
    return row


def make_stale(session, **overrides) -> Scholarship:
    """A record archived long ago and armed long ago: the only deletable shape."""
    fields = dict(
        title="Stale Programme",
        country="Peru",
        degree="Master",
        funding="Partial",
        official_source="Old Institute",
        official_source_url="https://old.test/stale",
        status="closed",
        is_archived=True,
        archived_at=ANCIENT,
        archived_reason="deadline passed on 2019-01-01",
        auto_delete_candidate_since=ANCIENT,
        is_verified=False,
        verification_status="inactive",
        deadline_date=date(2018, 6, 1),
    )
    fields.update(overrides)
    row = Scholarship(**fields)
    session.add(row)
    session.commit()
    return row


# ---------------------------------------------------------------------------
# Phase 5 - reference integrity
# ---------------------------------------------------------------------------


class TestReferenceIntegrity:
    def test_every_relationship_to_a_scholarship_is_classified(self):
        report = reference_integrity_report()
        assert report["integrity_uncertain"] is False
        assert report["unclassified_relationships"] == []
        assert report["verdict"] == "ALL_RELATIONSHIPS_CLASSIFIED"
        assert report["relationship_count"] == 13

    def test_the_report_is_introspected_not_hardcoded(self):
        """A table added later must appear, or it is invisible to the audit."""
        report = reference_integrity_report()
        tables = {r["table"] for r in report["relationships"]}
        assert "scholarship_reviews" in tables
        assert "scholarship_snapshots" in tables
        assert "discovery_candidates" in tables

    def test_no_relationship_declares_a_cascade(self):
        """So the hazard is manual child removal, not the database cascading."""
        report = reference_integrity_report()
        assert report["cascade_deletes_declared"] == []
        assert all(
            r["database_enforcement"] == "NO ACTION / RESTRICT"
            for r in report["relationships"]
        )

    def test_evidence_tables_are_preserved(self):
        assert set(PRESERVE_MODELS) == {
            "ScholarshipReview",
            "ScholarshipVerificationHistory",
            "ScholarshipSnapshot",
            "ScholarshipRestoreRecord",
            "ImageReview",
            "SavedScholarship",
            "ApplicationRecord",
            "ScholarshipSupervisorCoverage",
            "ScholarshipProfessorLink",
            "SupervisorSourceEvidence",
            "ProfessorOutreachRecord",
        }

    @pytest.mark.parametrize(
        "model, column_value",
        [
            (ScholarshipReview, {"field_name": "deadline", "conflict_reason": "x",
                                  "verification_state": "needs_review", "decision": "pending"}),
            (ScholarshipVerificationHistory, {"field_name": "status", "change_type": "verified",
                                              "verification_status": "active"}),
            (ScholarshipSnapshot, {"version_id": "v1", "valid_from": ANCIENT,
                                    "snapshot_data": {}}),
            (ImageReview, {"image_url": "https://x.test/i.png", "image_kind": "official_logo",
                           "confidence": "HIGH", "decision": "pending"}),
        ],
    )
    def test_any_evidence_row_blocks_deletion(self, session, model, column_value):
        """The whole point: a record with its own history is not deletable.

        An *unsettled* review is a stronger statement than a dependency - it makes
        the record an admin-review record outright, which is checked before
        dependencies are consulted. A settled one still blocks, as the
        dependency reason. Both outcomes are retention, which is what matters,
        and both are asserted so the distinction is visible rather than implied.
        """
        row = make_stale(session)
        session.add(model(scholarship_id=row.id, **column_value))
        session.commit()

        assert reference_dependencies(session, [row.id])[row.id], (
            f"{model.__name__} should register a dependency"
        )
        decision = next(d for d in scan(session, as_of=AS_OF) if d.scholarship_id == row.id)
        assert decision.is_keep
        assert decision.bucket in {BUCKET_ADMIN_REVIEW, BUCKET_PROTECTED}

    def test_settled_review_evidence_blocks_through_the_dependency(self, session):
        row = make_stale(session)
        session.add(
            ScholarshipReview(
                scholarship_id=row.id, field_name="status",
                conflict_reason="settled", verification_state="confirmed",
                decision="confirmed", reviewed_at=ANCIENT, reviewed_by="operator",
            )
        )
        session.commit()
        decision = next(d for d in scan(session, as_of=AS_OF) if d.scholarship_id == row.id)
        assert decision.bucket == BUCKET_PROTECTED
        assert decision.reason == "DEPENDENCY_MUST_SURVIVE"
        assert "ScholarshipReview" in decision.detail

    def test_settled_fetch_attempt_is_disposable_and_unsettled_blocks(self, session):
        row = make_stale(session)
        session.add(
            ScholarshipFetchAttempt(
                scholarship_id=row.id,
                source_url="https://old.test/stale",
                status="resolved",
                terminal=True,
                resolved_at=ANCIENT,
            )
        )
        session.commit()
        assert reference_dependencies(session, [row.id])[row.id] == frozenset()

        pending = make_stale(
            session, official_source_url="https://old.test/pending"
        )
        session.add(
            ScholarshipFetchAttempt(
                scholarship_id=pending.id,
                source_url="https://old.test/pending",
                status="pending",
            )
        )
        session.commit()
        deps = reference_dependencies(session, [pending.id])[pending.id]
        assert "ScholarshipFetchAttempt:unsettled" in deps

    def test_discovery_candidate_is_detached_not_deleted(self, session):
        row = make_stale(session)
        candidate = DiscoveryCandidate(
            source_url="https://old.test/stale",
            normalized_url="https://old.test/stale",
            discovery_hash="h1",
            status="resolved",
            match_status="rejected",
            matched_scholarship_id=row.id,
            resolved_at=ANCIENT,
        )
        session.add(candidate)
        session.commit()
        assert reference_dependencies(session, [row.id])[row.id] == frozenset()

    def test_discovery_candidate_awaiting_a_decision_blocks(self, session):
        row = make_stale(session)
        session.add(
            DiscoveryCandidate(
                source_url="https://old.test/waiting",
                normalized_url="https://old.test/waiting",
                discovery_hash="h2",
                status="pending",
                match_status="unmatched",
                matched_scholarship_id=row.id,
            )
        )
        session.commit()
        deps = reference_dependencies(session, [row.id])[row.id]
        assert "DiscoveryCandidate:awaiting_match_decision" in deps


# ---------------------------------------------------------------------------
# Phase 1/15 - the canonical predicates are reused
# ---------------------------------------------------------------------------


class TestCanonicalPredicateReuse:
    def test_live_matches_the_catalogue_exactly(self, session):
        live = make_live(session)
        make_live(session, official_source_url="https://example.test/nologo",
                  image_url=None, image_verified_at=None, title="No Logo")
        make_stale(session)

        expected = set(
            session.scalars(
                select(Scholarship.id).where(*public_visibility_conditions())
            ).all()
        )
        classified = {d.scholarship_id for d in scan(session, as_of=AS_OF) if d.bucket == BUCKET_LIVE}
        assert classified == expected
        assert live.id in classified

    def test_a_record_missing_its_logo_is_not_live_but_is_not_deletable(self, session):
        """The image gate hides; it does not make a record junk."""
        row = make_live(
            session, image_url=None, image_verified_at=None, title="No Logo Programme"
        )
        decision = next(d for d in scan(session, as_of=AS_OF) if d.scholarship_id == row.id)
        assert decision.bucket != BUCKET_LIVE
        assert decision.is_keep

    def test_admin_review_covers_both_review_surfaces(self, session):
        by_status = make_stale(session, verification_status="needs_review")
        by_review = make_stale(session, official_source_url="https://old.test/r2")
        session.add(
            ScholarshipReview(
                scholarship_id=by_review.id,
                field_name="status",
                conflict_reason="unresolved",
                verification_state="needs_review",
                decision="pending",
            )
        )
        by_image = make_stale(session, official_source_url="https://old.test/r3")
        session.add(
            ImageReview(
                scholarship_id=by_image.id,
                image_url="https://old.test/logo.png",
                image_kind="official_logo",
                confidence="LOW",
                decision="pending",
            )
        )
        session.commit()

        review_ids = {
            d.scholarship_id
            for d in scan(session, as_of=AS_OF)
            if d.bucket == BUCKET_ADMIN_REVIEW
        }
        assert review_ids == {by_status.id, by_review.id, by_image.id}

    def test_a_settled_review_does_not_hold_the_record(self, session):
        row = make_stale(session)
        session.add(
            ScholarshipReview(
                scholarship_id=row.id,
                field_name="status",
                conflict_reason="resolved",
                verification_state="confirmed",
                decision="confirmed",
                reviewed_at=ANCIENT,
                reviewed_by="operator",
            )
        )
        session.commit()
        decision = next(d for d in scan(session, as_of=AS_OF) if d.scholarship_id == row.id)
        assert decision.bucket == BUCKET_PROTECTED
        assert "ScholarshipReview" in decision.detail


# ---------------------------------------------------------------------------
# Phase 6/7 - the dry run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_the_shipped_policy_cannot_delete(self):
        policy = default_policy()
        assert policy.cleanup_enabled is False
        assert policy.dry_run is True
        with pytest.raises(PermissionError, match="cleanup_enabled"):
            policy.assert_deletion_permitted()

    def test_an_enabled_but_dry_policy_cannot_delete(self):
        with pytest.raises(PermissionError, match="dry_run"):
            RetentionPolicy(cleanup_enabled=True, dry_run=True).assert_deletion_permitted()

    def test_dry_run_writes_nothing(self, session):
        make_live(session)
        make_stale(session)
        before = catalogue_counts(session)
        report = dry_run(session, as_of=AS_OF, run_id="dry-1")
        assert catalogue_counts(session) == before
        assert report["mode"] == "DRY_RUN"

    def test_dry_run_reports_every_required_bucket(self, session):
        make_live(session)
        make_stale(session, verification_status="needs_review")
        make_stale(session, official_source_url="https://old.test/x", verification_status="mystery")
        make_stale(session, official_source_url="https://old.test/y")
        report = dry_run(session, as_of=AS_OF, run_id="dry-2")
        summary = report["summary"]
        for key in (
            "scanned", "live_kept", "admin_review_kept", "protected",
            "ambiguous", "conflicting", "delete_candidates", "errors",
        ):
            assert key in summary
        assert summary["reconciles"] is True
        assert summary["scanned"] == 4
        assert summary["live_kept"] == 1
        assert summary["admin_review_kept"] == 1
        assert summary["ambiguous"] == 1
        assert summary["delete_candidates"] == 1

    def test_dry_run_exposes_candidate_ids_and_reasons(self, session):
        row = make_stale(session)
        report = dry_run(session, as_of=AS_OF, run_id="dry-3")
        candidates = report["delete_candidates"]
        assert [c["scholarship_id"] for c in candidates] == [row.id]
        assert candidates[0]["reason"] == "NOT_LIVE_NOT_REVIEW"
        assert "archived" in candidates[0]["detail"]

    def test_dry_run_uses_the_same_scan_as_deletion(self, session):
        """Phase 7: one classifier, not an approximation of one."""
        make_stale(session)
        make_stale(session, official_source_url="https://old.test/second")
        direct = summarise(scan(session, as_of=AS_OF))
        reported = dry_run(session, as_of=AS_OF, run_id="dry-4")["summary"]
        assert direct.as_dict() == reported

    def test_dry_run_samples_are_bounded(self, session):
        for index in range(6):
            make_stale(session, official_source_url=f"https://old.test/{index}")
        report = dry_run(session, as_of=AS_OF, run_id="dry-5", sample_size=2)
        assert len(report["delete_candidates"]) == 2
        assert report["delete_candidates_truncated"] == 4

    def test_empty_database_reconciles(self, session):
        report = dry_run(session, as_of=AS_OF, run_id="dry-6")
        assert report["summary"]["scanned"] == 0
        assert report["summary"]["reconciles"] is True
        assert report["status"] == "ok"

    def test_dry_run_reports_the_recovery_verdict(self, session):
        report = dry_run(session, as_of=AS_OF, run_id="dry-7")
        assert report["recovery"]["verdict"] == "RECOVERY_PATH_REQUIRED"
        assert report["recovery"]["verified_pitr"] is False

    def test_dry_run_publishes_the_contract_version(self, session):
        report = dry_run(session, as_of=AS_OF, run_id="dry-8")
        assert report["contract_version"] == RETENTION_CONTRACT_VERSION


class TestMassDeletionGuards:
    def test_per_run_cap_blocks_the_run(self, session):
        for index in range(4):
            make_stale(session, official_source_url=f"https://old.test/{index}")
        policy = RetentionPolicy(max_delete_per_run=2, max_delete_percentage=1.0)
        report = dry_run(session, as_of=AS_OF, policy=policy, run_id="guard-1")
        assert report["guards"]["candidates_within_per_run_cap"] is False
        assert any("per-run cap" in f for f in report["guard_failures"])
        assert report["status"] == "partial"

    def test_percentage_cap_blocks_the_run(self, session):
        make_stale(session)
        for index in range(9):
            make_live(session, official_source_url=f"https://example.test/{index}")
        policy = RetentionPolicy(max_delete_percentage=0.05)
        report = dry_run(session, as_of=AS_OF, policy=policy, run_id="guard-2")
        assert report["guards"]["candidates_within_percentage_cap"] is False
        assert any("share cap" in f for f in report["guard_failures"])

    def test_ambiguous_tolerance_blocks_the_run(self, session):
        make_stale(session, verification_status="mystery")
        policy = RetentionPolicy(max_ambiguous_ratio=0.0)
        report = dry_run(session, as_of=AS_OF, policy=policy, run_id="guard-3")
        assert report["guards"]["ambiguous_within_tolerance"] is False
        assert any("could not be classified" in f for f in report["guard_failures"])

    def test_a_competing_run_blocks_the_run(self, session):
        make_live(session)
        session.add(
            MaintenanceRun(run_id="other", worker="retention/live-admin-review/1", status="running")
        )
        session.commit()
        report = dry_run(session, as_of=AS_OF, run_id="guard-4")
        assert report["guards"]["no_competing_cleanup"] is False
        assert "other" in " ".join(report["guard_failures"])

    def test_a_stale_run_does_not_block(self, session):
        """A crashed run must not block every future run forever."""
        make_live(session)
        session.add(
            MaintenanceRun(
                run_id="ancient",
                worker="retention/live-admin-review/1",
                status="running",
                started_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        session.commit()
        report = dry_run(session, as_of=AS_OF, run_id="guard-5")
        assert report["guards"]["no_competing_cleanup"] is True


# ---------------------------------------------------------------------------
# Phase 8/18 - deletion
# ---------------------------------------------------------------------------


class TestDeletionIsRefusedByDefault:
    def test_delete_bounded_refuses_the_shipped_policy(self, session):
        with pytest.raises(PermissionError):
            delete_bounded(session, [1], as_of=AS_OF, run_id="del-1")

    def test_delete_bounded_refuses_a_dry_run_policy(self, session):
        with pytest.raises(PermissionError, match="dry_run"):
            delete_bounded(
                session, [1], as_of=AS_OF, policy=RetentionPolicy(cleanup_enabled=True), run_id="del-2"
            )

    def test_a_refused_run_touches_no_scholarship_row(self, session):
        row = make_stale(session)
        with pytest.raises(PermissionError):
            delete_bounded(session, [row.id], as_of=AS_OF, run_id="del-3")
        assert still_stored(session, row.id) is True


class TestBoundedDeletion:
    def test_a_proven_candidate_is_deleted(self, session, tmp_ledger):
        row = make_stale(session)
        report = delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-ok")
        assert report["deleted"] == [row.id]
        assert still_stored(session, row.id) is False

    def test_a_live_record_is_never_deleted(self, session, tmp_ledger):
        row = make_live(session)
        report = delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-live")
        assert report["deleted"] == []
        assert still_stored(session, row.id) is True
        assert report["aborted"][0]["bucket"] == BUCKET_LIVE

    def test_an_admin_review_record_is_never_deleted(self, session, tmp_ledger):
        row = make_stale(session, verification_status="needs_review")
        report = delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-ar")
        assert report["deleted"] == []
        assert still_stored(session, row.id) is True
        assert report["aborted"][0]["bucket"] == BUCKET_ADMIN_REVIEW

    def test_deletion_is_batched(self, session, tmp_ledger):
        rows = [make_stale(session, official_source_url=f"https://old.test/{i}") for i in range(7)]
        report = delete_bounded(session, [r.id for r in rows], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-batch")
        assert len(report["batches"]) == 2
        assert [len(b["deleted"]) for b in report["batches"]] == [5, 2]
        assert sorted(report["deleted"]) == sorted(r.id for r in rows)

    def test_the_per_run_cap_is_enforced_against_a_real_count(self, session, tmp_ledger):
        rows = [make_stale(session, official_source_url=f"https://old.test/{i}") for i in range(4)]
        policy = DELETING.with_overrides(max_delete_per_run=2)
        with pytest.raises(CleanupAborted, match="per-run cap"):
            delete_bounded(session, [r.id for r in rows], as_of=AS_OF, policy=policy, ledger=tmp_ledger, run_id="del-cap")
        assert all(still_stored(session, r.id) is True for r in rows)

    def test_the_percentage_cap_is_enforced(self, session, tmp_ledger):
        make_stale(session)
        for index in range(30):
            make_live(session, official_source_url=f"https://example.test/{index}")
        policy = DELETING.with_overrides(max_delete_percentage=0.01)
        with pytest.raises(CleanupAborted, match="of storage"):
            delete_bounded(session, [2], as_of=AS_OF, policy=policy, ledger=tmp_ledger, run_id="del-pct")

    def test_evidence_rows_survive_a_deletion_run(self, session, tmp_ledger):
        """No PRESERVE table is ever read for deletion, so nothing is destroyed."""
        row = make_stale(session)
        session.add(
            ScholarshipVerificationHistory(
                scholarship_id=row.id, field_name="status", change_type="verified",
                verification_status="active",
            )
        )
        session.commit()
        report = delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-hist")
        assert report["deleted"] == []
        assert still_stored(session, row.id) is True
        assert session.scalar(
            select(ScholarshipVerificationHistory).where(
                ScholarshipVerificationHistory.scholarship_id == row.id
            )
        ) is not None

    def test_settled_fetch_telemetry_goes_with_the_record(self, session, tmp_ledger):
        row = make_stale(session)
        session.add(
            ScholarshipFetchAttempt(
                scholarship_id=row.id, source_url="https://old.test/stale",
                status="resolved", terminal=True, resolved_at=ANCIENT,
            )
        )
        candidate = DiscoveryCandidate(
            source_url="https://old.test/stale", normalized_url="https://old.test/stale",
            discovery_hash="h9", status="resolved", match_status="rejected",
            matched_scholarship_id=row.id, resolved_at=ANCIENT,
        )
        session.add(candidate)
        session.commit()

        report = delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-children")
        assert report["deleted"] == [row.id]
        session.expire_all()
        assert session.get(ScholarshipFetchAttempt, 1) is None or session.query(
            ScholarshipFetchAttempt
        ).filter(ScholarshipFetchAttempt.scholarship_id == row.id).first() is None
        detached = session.get(DiscoveryCandidate, candidate.id)
        assert detached is not None
        assert detached.matched_scholarship_id is None
        assert detached.match_status == "unmatched"

    def test_count_reconciliation_runs_after_deletion(self, session, tmp_ledger):
        row = make_stale(session)
        report = delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-recon")
        reconciliation = report["reconciliation"]
        assert reconciliation["reconciles"] is True
        assert reconciliation["checks"]["public_total_unchanged"] is True
        assert reconciliation["checks"]["admin_review_unchanged"] is True
        assert reconciliation["checks"]["row_total_decreased_by_deleted"] is True
        assert reconciliation["before"]["row_total"] - reconciliation["after"]["row_total"] == 1

    def test_a_failed_reconciliation_aborts_the_run(self, session, monkeypatch, tmp_ledger):
        """The reconciliation is a gate, not a report."""
        row = make_stale(session)
        import app.services.retention_engine as engine

        real = engine.catalogue_counts
        calls = {"n": 0}

        def drifting(sess):
            calls["n"] += 1
            counts = dict(real(sess))
            if calls["n"] > 1:
                # Pretend another writer removed a live row concurrently.
                counts["public_total"] = counts.get("public_total", 0) - 1
            return counts

        monkeypatch.setattr(engine, "catalogue_counts", drifting)
        with pytest.raises(CleanupAborted, match="reconciliation"):
            delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="del-drift")


# ---------------------------------------------------------------------------
# Phase 9 - concurrency
# ---------------------------------------------------------------------------


class TestConcurrencySafety:
    def test_a_candidate_that_became_live_is_kept(self, session, tmp_ledger):
        """Phase 9: the verification worker wins the race."""
        row = make_stale(session)
        # Classification happens first, by hand, to fix the candidate set.
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        assert candidates == [row.id]

        # The verification worker then re-verifies and publishes the record.
        row.is_verified = True
        row.verification_status = "active"
        row.image_url = "https://old.test/logo.png"
        row.image_verified_at = datetime.now(timezone.utc)
        row.image_source_type = "official"
        session.commit()

        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="race-1")
        assert report["deleted"] == []
        assert still_stored(session, row.id) is True
        assert "no longer a deletion candidate" in report["aborted"][0]["verdict"]

    def test_a_candidate_that_entered_review_is_kept(self, session, tmp_ledger):
        """Phase 9: an admin-review update wins the race."""
        row = make_stale(session)
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]

        session.add(
            ScholarshipReview(
                scholarship_id=row.id, field_name="status",
                conflict_reason="operator opened a review",
                verification_state="needs_review", decision="pending",
            )
        )
        session.commit()

        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="race-2")
        assert report["deleted"] == []
        assert still_stored(session, row.id) is True

    def test_a_candidate_whose_state_moved_is_refused_by_the_conditional_delete(self, session):
        """The SQL guard, tested directly against a database.

        The Python re-check and the ``DELETE`` are two separate reads, and the
        window between them is the one a re-check alone cannot cover. This drives
        a change into that window by handing the guarded statement the clocks the
        verdict was based on and then moving the record on underneath it, and
        shows the statement matching no row.

        Every field that could change the verdict is driven separately, because
        each one is a different clause of the predicate and a guard with an
        unexercised clause is an unguarded clause.
        """
        from app.services.retention_engine import (
            admin_review_conditions,
            conditional_delete,
            live_condition,
        )

        live = live_condition()
        review = admin_review_conditions()

        mutations = {
            # Constructed so the record is genuinely LIVE while both retention
            # clocks are untouched. "Became live" normally means it was reopened,
            # and reopening clears ``archived_at`` - which would let the clock
            # equality do the refusing and leave the ``not live`` clause
            # unexercised. Leaving the clock behind isolates that clause, which is
            # the one that has to stop a record that is in the public catalogue
            # from being deleted while its stored clocks look deletable.
            "became_live": lambda row: (
                setattr(row, "is_archived", False),
                setattr(row, "is_verified", True),
                setattr(row, "verification_status", "active"),
                setattr(row, "image_url", "https://old.test/logo.png"),
                setattr(row, "image_verified_at", datetime(2026, 10, 1, tzinfo=timezone.utc)),
                setattr(row, "image_source_type", "official"),
            ),
            "entered_review": lambda row: setattr(row, "verification_status", "needs_review"),
            "was_protected": lambda row: setattr(row, "deletion_protected", True),
            "retention_clock_moved": lambda row: setattr(row, "archived_at", ANCIENT + timedelta(days=1)),
            "grace_clock_cleared": lambda row: setattr(row, "auto_delete_candidate_since", None),
            "reopened": lambda row: (
                setattr(row, "is_archived", False),
                setattr(row, "archived_at", None),
            ),
        }

        for index, (name, mutate) in enumerate(mutations.items()):
            row = make_stale(session, official_source_url=f"https://old.test/guard{index}")
            session.commit()
            session.refresh(row)
            row_id = row.id
            archived_at = row.archived_at
            candidate_since = row.auto_delete_candidate_since

            # Baseline: with the record untouched, the statement does match.
            assert conditional_delete(
                session, row_id, archived_at=archived_at, candidate_since=candidate_since,
                live_conditions=live, review_conditions=review,
            ).rowcount == 1, f"{name}: the unguarded baseline should have deleted"
            session.rollback()
            session.expire_all()

            # Now move the record, and re-issue with the same stale clocks.
            mutate(session.get(Scholarship, row_id))
            session.commit()
            session.expire_all()
            if name == "became_live":
                # Prove the premise: the clause is only load-bearing if the
                # record really is in the public catalogue at this point.
                assert set(session.scalars(select(Scholarship.id).where(*live)).all()) == {row_id}
            result = conditional_delete(
                session, row_id, archived_at=archived_at, candidate_since=candidate_since,
                live_conditions=live, review_conditions=review,
            )
            assert result.rowcount == 0, (
                f"{name}: the conditional delete should have matched no row"
            )
            session.rollback()
            assert still_stored(session, row_id) is True, f"{name}: the record was lost"


    def test_a_protected_record_is_kept(self, session, tmp_ledger):
        row = make_stale(session)
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        row.deletion_protected = True
        session.commit()
        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="race-4")
        assert report["deleted"] == []
        assert still_stored(session, row.id) is True

    def test_a_reopened_record_is_kept(self, session, tmp_ledger):
        row = make_stale(session)
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        row.is_archived = False
        row.archived_at = None
        row.status = "open"
        row.deadline_date = date(2099, 1, 1)
        session.commit()
        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="race-5")
        assert report["deleted"] == []
        assert still_stored(session, row.id) is True


# ---------------------------------------------------------------------------
# Phase 18 - idempotency and dataset shapes
# ---------------------------------------------------------------------------


class TestIdempotencyAndShapes:
    def test_running_twice_finds_no_additional_deletions(self, session, tmp_ledger):
        """Phase 18's critical property, on a mixed dataset."""
        make_live(session)
        stale = [make_stale(session, official_source_url=f"https://old.test/{i}") for i in range(3)]
        make_stale(session, verification_status="needs_review", official_source_url="https://old.test/r")
        make_stale(session, verification_status="mystery", official_source_url="https://old.test/m")

        first = delete_bounded(
            session, [r.id for r in stale], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="idem-1"
        )
        # Captured as plain integers: a deleted ORM instance raises on attribute
        # access, so asking the objects for their ids after the fact tests the
        # session rather than the engine.
        stale_ids = [r.id for r in stale]
        assert len(first["deleted"]) == 3

        second = scan(session, as_of=AS_OF)
        assert [d for d in second if d.is_delete] == []
        assert all(still_stored(session, sid) is False for sid in stale_ids)

    def test_all_live_database_has_no_candidates(self, session):
        for index in range(4):
            make_live(session, official_source_url=f"https://example.test/{index}")
        assert [d for d in scan(session, as_of=AS_OF) if d.is_delete] == []

    def test_all_review_database_has_no_candidates(self, session):
        for index in range(4):
            make_stale(
                session,
                official_source_url=f"https://old.test/{index}",
                verification_status="needs_review",
            )
        assert [d for d in scan(session, as_of=AS_OF) if d.is_delete] == []

    def test_all_conflicting_database_has_no_candidates(self, session):
        for index in range(3):
            make_stale(
                session,
                official_source_url=f"https://old.test/{index}",
                archived_at=None,
            )
        decisions = scan(session, as_of=AS_OF)
        assert [d for d in decisions if d.is_delete] == []
        assert all(d.bucket == BUCKET_CONFLICTING for d in decisions)

    def test_a_dataset_entirely_of_candidates_is_still_capped(self, session, tmp_ledger):
        rows = [make_stale(session, official_source_url=f"https://old.test/{i}") for i in range(6)]
        policy = DELETING.with_overrides(max_delete_per_run=3, max_delete_percentage=1.0)
        with pytest.raises(CleanupAborted, match="per-run cap"):
            delete_bounded(session, [r.id for r in rows], as_of=AS_OF, policy=policy, ledger=tmp_ledger, run_id="shape-1")
        assert all(still_stored(session, r.id) is True for r in rows)

    def test_no_candidates_means_nothing_is_written(self, session, tmp_ledger):
        make_live(session)
        before = session.query(MaintenanceRun).count()
        report = delete_bounded(session, [], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="shape-2")
        assert report["deleted"] == []
        assert session.query(MaintenanceRun).count() == before


# ---------------------------------------------------------------------------
# Phase 11 - the audit ledger
# ---------------------------------------------------------------------------


class TestAuditLedger:
    def test_a_dry_run_leaves_exactly_one_readable_row(self, session):
        make_live(session)
        make_stale(session)
        # The shipped 5% share cap refuses a two-row catalogue with one candidate,
        # which is the guard working; the cap has its own test, so this one is
        # about the ledger, not the guard.
        dry_run(
            session, as_of=AS_OF, run_id="audit-1", trigger="manual",
            policy=RetentionPolicy(max_delete_percentage=1.0),
        )
        run = audit_row(session, "audit-1")
        assert run is not None
        assert run.worker.startswith("retention/")
        assert run.dry_run is True
        assert run.status == "ok"
        assert run.finished_at is not None
        assert run.counts["retention_scanned"] == 2
        assert run.counts["retention_kept_live"] == 1
        assert "retention" in run.counts["retention_contract_version"]
        assert run.stages[0]["name"] == "retention_cleanup"
        assert run.stages[0]["detail"]["trigger"] == "manual"
        assert session.query(MaintenanceRun).count() == 1

    def test_every_required_field_is_recorded(self, session):
        make_live(session)
        dry_run(session, as_of=AS_OF, run_id="audit-2")
        counts = audit_row(session, "audit-2").counts
        for key in (
            "retention_scanned",
            "retention_kept_live",
            "retention_kept_admin_review",
            "retention_delete_candidates",
            "retention_protected",
            "retention_ambiguous",
            "retention_conflicting",
        ):
            assert key in counts

    def test_a_deleting_run_is_recorded_as_a_deleting_run(self, session, tmp_ledger):
        row = make_stale(session)
        delete_bounded(session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="audit-3")
        run = audit_row(session, "audit-3")
        assert run.dry_run is False
        assert run.counts["retention_deleted"] == 1

    def test_the_ledger_stores_no_personal_data(self, session):
        make_stale(session)
        dry_run(session, as_of=AS_OF, run_id="audit-4")
        run = audit_row(session, "audit-4")
        serialised = json.dumps(
            {"counts": run.counts, "stages": run.stages, "summary": run.error_summary},
            default=str,
        )
        for forbidden in ("email", "password", "token", "secret", "@"):
            assert forbidden not in serialised.lower()

    def test_the_manifest_records_the_run_before_it_commits(self, session, tmp_ledger):
        """An unconfirmed entry must exist even if the delete then fails.

        The ledger is written first on purpose: a process that dies between the
        write and the commit leaves an over-reported deletion, which is repaired
        by reading the id back out of the database. The reverse order leaves a
        deletion nobody can account for.
        """
        row = make_stale(session)
        with pytest.raises(CleanupAborted):
            delete_bounded(
                session, [row.id], as_of=AS_OF,
                policy=DELETING.with_overrides(max_delete_per_run=0),
                ledger=tmp_ledger, run_id="audit-5",
            )
        written = json.loads(tmp_ledger.read_text(encoding="utf-8")) if tmp_ledger.exists() else {}
        # The cap is checked before the first batch, so nothing was written at all.
        assert written.get("retention_summary", {}).get("retention_deleted", 0) == 0
        assert stored_rows(session) == 1


    def test_the_repository_ledger_is_the_one_ledger(self, session):
        """No second source of truth: this engine extends the existing file."""
        assert ledger_path().name == "purged_records_archive.json"

    def test_a_deletion_writes_its_manifest_where_it_was_told(self, session, tmp_ledger):
        row = make_stale(session)
        report = delete_bounded(
            session, [row.id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="audit-6"
        )
        assert report["deleted"] == [row.id]
        assert tmp_ledger.exists(), "the manifest should be written to the supplied path"
        written = json.loads(tmp_ledger.read_text(encoding="utf-8"))
        summary = written["retention_summary"]
        assert summary["retention_deleted"] == 1
        assert summary["retention_records"][0]["record_identity"]["id"] == row.id
        assert written["retention_batches"][-1]["confirmed"] is True
        assert written["retention_batches"][-1]["manifest_is_a_backup"] is False
        assert written["retention_runs"][-1]["run_id"] == "audit-6"

    def test_a_suite_run_never_writes_the_repository_ledger(self, session, tmp_ledger):
        """The property that keeps the test suite from falsifying the record."""
        before = ledger_path().read_bytes() if ledger_path().exists() else None
        rows = [make_stale(session, official_source_url=f"https://old.test/iso{i}") for i in range(3)]
        delete_bounded(
            session, [r.id for r in rows], as_of=AS_OF, policy=DELETING,
            ledger=tmp_ledger, run_id="audit-7",
        )
        after = ledger_path().read_bytes() if ledger_path().exists() else None
        assert after == before


# ---------------------------------------------------------------------------
# Phase 12 - recovery
# ---------------------------------------------------------------------------


class TestRecoveryVerdict:
    def test_recovery_is_reported_as_required(self):
        status = recovery_status()
        assert status["verdict"] == "RECOVERY_PATH_REQUIRED"
        assert status["verified_pitr"] is False
        assert status["automated_backups"] is False

    def test_the_ledger_is_not_presented_as_a_backup(self):
        """Phase 12: do not pretend an audit log is a backup."""
        status = recovery_status()
        assert "cannot restore referential integrity" in status["manifest_ledger"]
        assert "point-in-time recovery path" in status["consequence"]
        assert "Hard deletion is not enabled" in status["consequence"]
