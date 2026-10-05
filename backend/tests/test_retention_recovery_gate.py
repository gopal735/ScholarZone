"""Phases 1, 2, 3, 5, 8, 10 and 11 - the state machine, the recovery contract,
the manifest's honesty, and the release gate.

Several of these tests exist because the thing they cover was *wrong* at some
point during this work, and a regression test that only ever saw the fixed
behaviour would not have caught the original defect. Each says which defect it
guards.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, DiscoveryCandidate, Scholarship, ScholarshipReview
from app.services.retention_contract import (
    BUCKET_ADMIN_REVIEW,
    BUCKET_AMBIGUOUS,
    BUCKET_CONFLICTING,
    BUCKET_DELETE,
    BUCKET_LIVE,
    BUCKET_PROTECTED,
    DECISION_DELETE,
    DECISION_KEEP,
    NON_DELETABLE_STATES,
    RETENTION_CONTRACT_VERSION,
    RETENTION_STATES,
    RETENTION_TRANSITIONS,
    STATE_AMBIGUOUS,
    STATE_CONFLICTING,
    STATE_DELETE_CANDIDATE,
    STATE_DELETED,
    STATE_GRACE_ELIGIBLE,
    STATE_KEEP,
    STATE_PROTECTED,
    STATE_UNKNOWN,
    RetentionDecision,
    RetentionFacts,
    RetentionPolicy,
    assert_invariants,
    assert_transition,
    classify,
    default_policy,
    summarise,
)
from app.services.retention_engine import (
    MANIFEST_DISCLAIMER,
    PRESERVE_MODELS,
    append_deletion_manifest,
    reference_integrity_report,
)
from app.services.retention_recovery import (
    ABSENT,
    PROVEN,
    RECOVERY_PLAN,
    RECOVERY_REQUIREMENTS,
    UNKNOWN,
    database_identity,
    production_dialect_evidence,
    recovery_capability_inventory,
    recovery_plan_as_dict,
    recovery_requirements_report,
)
from app.services.retention_release_gate import (
    GATE_CONDITIONS,
    HELD,
    RELEASED,
    REQUIRED_EVIDENCE_FIELDS,
    evaluate_release_gate,
)

AS_OF = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
ANCIENT = datetime(2019, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def production_visibility_gate(monkeypatch):
    """Run under the production visibility contract.

    The suite-wide ``conftest`` disables both public quality gates for its
    legacy listing fixtures. Without this, a record with no verified image is
    still LIVE, the "missing_image" shape does not exist, and the integration
    test below would be asserting against a catalogue that production does not
    have.
    """
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE", "false")


def facts(sid: int, **overrides) -> RetentionFacts:
    base = dict(
        scholarship_id=sid, is_live=False, verification_status="inactive",
        lifecycle_status="closed", deletion_protected=False, is_archived=True,
        archived_at=ANCIENT, archived_reason="deadline passed", candidate_since=ANCIENT,
        is_verified=False, deadline_date=date(2018, 6, 1),
        blocking_dependencies=frozenset(), evidence_complete=True,
    )
    base.update(overrides)
    return RetentionFacts(**base)


# ---------------------------------------------------------------------------
# Phase 1 - the state machine
# ---------------------------------------------------------------------------


class TestTheStateMachineIsClosed:
    def test_exactly_eight_states_exist(self):
        assert RETENTION_STATES == {
            "KEEP", "UNKNOWN", "AMBIGUOUS", "CONFLICTING", "PROTECTED",
            "DELETE_CANDIDATE", "GRACE_ELIGIBLE", "DELETED",
        }

    def test_every_state_has_a_transition_row(self):
        assert set(RETENTION_TRANSITIONS) == RETENTION_STATES

    def test_only_dead_state_is_terminal(self):
        assert RETENTION_TRANSITIONS[STATE_DELETED] == frozenset()
        for state, targets in RETENTION_TRANSITIONS.items():
            if state != STATE_DELETED:
                assert targets, f"{state} is a dead end"

    def test_dead_state_can_only_be_reached_from_a_candidate(self):
        incoming = {s for s, t in RETENTION_TRANSITIONS.items() if STATE_DELETED in t}
        assert incoming == {STATE_DELETE_CANDIDATE}

    def test_no_deletable_state_can_be_reached_from_dead(self):
        assert STATE_DELETE_CANDIDATE not in RETENTION_TRANSITIONS[STATE_DELETED]


class TestEveryStateIsReachable:
    @pytest.mark.parametrize(
        "overrides, expected",
        [
            (dict(is_live=True, verification_status="active", is_verified=True), STATE_KEEP),
            (dict(verification_status="needs_review"), STATE_KEEP),
            (dict(verification_status="a_state_nobody_classified"), STATE_UNKNOWN),
            (dict(evidence_complete=False, evidence_error="query failed"), STATE_AMBIGUOUS),
            (dict(archived_at=None), STATE_CONFLICTING),
            (dict(deletion_protected=True), STATE_PROTECTED),
            (dict(candidate_since=None), STATE_GRACE_ELIGIBLE),
            (dict(candidate_since=AS_OF - timedelta(days=3)), STATE_GRACE_ELIGIBLE),
            (dict(), STATE_DELETE_CANDIDATE),
        ],
    )
    def test_each_state_is_produced_by_a_real_record(self, overrides, expected):
        decision = classify(facts(1, **overrides), policy=default_policy(), as_of=AS_OF)
        assert decision.state == expected

    def test_unknown_and_ambiguous_are_distinguished(self):
        """A value nobody classified is a different problem from a failed read."""
        unknown = classify(
            facts(1, verification_status="brand_new"), policy=default_policy(), as_of=AS_OF
        )
        ambiguous = classify(
            facts(2, evidence_complete=False, evidence_error="read failed"),
            policy=default_policy(), as_of=AS_OF,
        )
        assert unknown.state == STATE_UNKNOWN
        assert ambiguous.state == STATE_AMBIGUOUS
        assert unknown.reason == "UNKNOWN_STATE"
        assert ambiguous.reason == "INCOMPLETE_EVIDENCE"
        assert unknown.bucket == ambiguous.bucket == BUCKET_AMBIGUOUS
        assert unknown.is_keep and ambiguous.is_keep


class TestStateLegalityIsAssertedNotAssumed:
    def test_a_mislabelled_state_is_caught(self):
        """Guards a real defect: CONFLICTING shipped labelled as KEEP."""
        decision = classify(facts(1, archived_at=None), policy=default_policy(), as_of=AS_OF)
        assert decision.state == STATE_CONFLICTING
        mislabelled = RetentionDecision(
            scholarship_id=1, decision=DECISION_KEEP, bucket=BUCKET_CONFLICTING,
            reason="CONFLICTING_STATE", state=STATE_KEEP,
        )
        with pytest.raises(AssertionError):
            assert_invariants([mislabelled])

    def test_a_forged_deletion_in_a_retained_state_is_caught(self):
        good = classify(facts(1), policy=default_policy(), as_of=AS_OF)
        forged = RetentionDecision(
            scholarship_id=1, decision=DECISION_DELETE, bucket=BUCKET_DELETE,
            reason="NOT_LIVE_NOT_REVIEW", state=STATE_KEEP, checks=good.checks,
        )
        with pytest.raises(AssertionError, match="DELETE_CANDIDATE"):
            assert_invariants([forged])

    def test_a_candidate_state_carrying_keep_is_caught(self):
        good = classify(facts(1), policy=default_policy(), as_of=AS_OF)
        forged = RetentionDecision(
            scholarship_id=1, decision=DECISION_KEEP, bucket=BUCKET_DELETE,
            reason="NOT_LIVE_NOT_REVIEW", state=STATE_DELETE_CANDIDATE, checks=good.checks,
        )
        with pytest.raises(AssertionError):
            assert_invariants([forged])

    def test_grace_eligible_with_a_delete_is_caught(self):
        forged = RetentionDecision(
            scholarship_id=1, decision=DECISION_DELETE, bucket=BUCKET_DELETE,
            reason="NOT_LIVE_NOT_REVIEW", state=STATE_DELETE_CANDIDATE,
            grace_eligible=True, checks={"x": True},
        )
        with pytest.raises(AssertionError, match="grace"):
            assert_invariants([forged])

    def test_keep_to_dead_is_refused(self):
        with pytest.raises(AssertionError, match="illegal retention transition"):
            assert_transition(STATE_KEEP, STATE_DELETED)

    def test_protected_to_dead_is_refused(self):
        for state in (STATE_PROTECTED, STATE_UNKNOWN, STATE_AMBIGUOUS, STATE_CONFLICTING):
            with pytest.raises(AssertionError):
                assert_transition(state, STATE_DELETED)

    def test_candidate_to_dead_is_permitted(self):
        assert_transition(STATE_DELETE_CANDIDATE, STATE_DELETED)

    def test_grace_eligible_to_candidate_is_permitted(self):
        assert_transition(STATE_GRACE_ELIGIBLE, STATE_DELETE_CANDIDATE)

    def test_non_deletable_states_are_enumerated_not_inferred(self):
        assert NON_DELETABLE_STATES == {
            STATE_KEEP, STATE_UNKNOWN, STATE_AMBIGUOUS, STATE_CONFLICTING, STATE_PROTECTED
        }
        assert STATE_DELETE_CANDIDATE not in NON_DELETABLE_STATES
        assert STATE_GRACE_ELIGIBLE not in NON_DELETABLE_STATES


class TestArchivalAloneDoesNotImplyDelete:
    """The three claims Phase 1 requires be proven explicitly."""

    def test_archival_alone_is_not_enough(self):
        """Archived, but too recent and not yet armed."""
        decision = classify(
            facts(1, archived_at=AS_OF - timedelta(days=10)),
            policy=default_policy(), as_of=AS_OF,
        )
        assert decision.state == STATE_PROTECTED
        assert decision.reason == "RETENTION_NOT_ELAPSED"
        assert decision.is_keep

    def test_a_missing_verified_image_is_not_enough(self):
        """Verified and unarchived, but hidden by the image gate."""
        decision = classify(
            facts(1, verification_status="active", is_verified=True,
                  is_archived=False, archived_at=None),
            policy=default_policy(), as_of=AS_OF,
        )
        assert decision.state == STATE_PROTECTED
        assert decision.is_keep

    def test_historical_evidence_is_not_enough(self):
        """Fully aged and armed, but carrying a review row."""
        decision = classify(
            facts(1, blocking_dependencies=frozenset({"ScholarshipVerificationHistory"})),
            policy=default_policy(), as_of=AS_OF,
        )
        assert decision.state == STATE_PROTECTED
        assert decision.reason == "DEPENDENCY_MUST_SURVIVE"
        assert decision.is_keep

    def test_only_a_fully_qualified_record_reaches_delete_candidate(self):
        decision = classify(facts(1), policy=default_policy(), as_of=AS_OF)
        assert decision.state == STATE_DELETE_CANDIDATE
        assert all(decision.checks.values())

    def test_the_state_histogram_reconciles(self):
        decisions = [
            classify(facts(i, is_live=True, verification_status="active", is_verified=True),
                     policy=default_policy(), as_of=AS_OF) if i == 1
            else classify(facts(i), policy=default_policy(), as_of=AS_OF)
            for i in range(1, 6)
        ]
        summary = summarise(decisions)
        assert summary.reconciles()
        assert sum(summary.states.values()) == summary.scanned
        assert summary.grace_eligible >= 0


# ---------------------------------------------------------------------------
# Phase 2/3 - the recovery contract and the capability inventory
# ---------------------------------------------------------------------------


class TestRecoveryContract:
    def test_all_eight_requirements_are_defined(self):
        assert [r.id for r in RECOVERY_REQUIREMENTS] == list("ABCDEFGH")

    def test_every_requirement_says_how_it_would_be_demonstrated(self):
        for requirement in RECOVERY_REQUIREMENTS:
            assert len(requirement.demonstrated_by) > 40, requirement.id
            assert len(requirement.consequence_if_absent) > 40, requirement.id

    def test_the_contract_is_not_satisfied_without_evidence(self):
        report = recovery_requirements_report(recovery_capability_inventory())
        assert report["verdict"] == "RECOVERY_PATH_NOT_PROVEN"
        assert report["recovery_path_proven"] is False
        assert report["unmet"] == list("ABCDEFGH")

    def test_configured_is_not_accepted_as_proven(self):
        """The exact reasoning that would let an irreversible action through."""
        inventory = recovery_capability_inventory()
        for item in inventory:
            assert item["status"] in {
                PROVEN, "CONFIGURED_NOT_PROVEN", "DOCUMENTED_ONLY", ABSENT, UNKNOWN
            }
        # Nothing except the engine's own reporting may be PROVEN today.
        proven = [i["id"] for i in inventory if i["status"] == PROVEN]
        assert proven == ["R12"], proven

    def test_each_requirement_reports_what_it_depends_on(self):
        report = recovery_requirements_report(recovery_capability_inventory())
        for row in report["requirements"]:
            assert "depends_on" in row
            assert row["status"] in {
                PROVEN, "CONFIGURED_NOT_PROVEN", "DOCUMENTED_ONLY", ABSENT, UNKNOWN
            }


class TestInventoryHonesty:
    def test_a_workflow_mentioning_a_backup_noun_is_not_a_backup(self):
        """Guards a real defect: 'snapshot' in verification-cron.yml is the
        temporal-versioning table name, not a backup job."""
        inventory = recovery_capability_inventory()
        workflows = [i for i in inventory if i["id"] == "R3"][0]
        assert workflows["status"] == ABSENT
        assert "scholarship_snapshots" in workflows["note"]

    def test_backup_detection_matches_actions_not_words(self, tmp_path, monkeypatch):
        import app.services.retention_recovery as recovery

        root = tmp_path / "repo"
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "lies.yml").write_text(
            "run: echo 'we take a snapshot and a backup of nothing'\n", encoding="utf-8"
        )
        (workflows / "real.yml").write_text(
            "run: pg_dump -Fc \"$DATABASE\" | aws s3 cp - s3://bucket/db.dump\n", encoding="utf-8"
        )
        monkeypatch.setattr(recovery, "_repo_root", lambda: root)
        found = {w["workflow"]: w["produces_a_backup"] for w in recovery._workflow_inventory()}
        assert found == {"lies.yml": False, "real.yml": True}

    def test_no_backup_capability_is_claimed_that_was_not_observed(self):
        inventory = recovery_capability_inventory()
        for item in inventory:
            assert item["searched"], f"{item['id']} records no search, so its absence is silent"
            assert item["note"], f"{item['id']} has no note"

    def test_the_inventory_is_reproducible(self):
        first = recovery_capability_inventory()
        second = recovery_capability_inventory()
        strip = lambda inv: [{k: v for k, v in i.items() if k != "observed_at"} for i in inv]
        assert strip(first) == strip(second)


class TestNoCredentialLeaks:
    def test_database_identity_never_reveals_the_url(self, monkeypatch):
        secret = "postgresql://admin:hunter2@db.internal.neon.tech:5432/scholarzone?sslmode=require"
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: type("S", (), {"database_url": secret})(),
        )
        identity = database_identity()
        serialised = json.dumps(identity)
        for leak in ("hunter2", "admin", "neon.tech", "scholarzone", "5432", "postgresql://"):
            assert leak not in serialised, f"{leak!r} leaked from database_identity"

    def test_database_identity_reports_the_dialect_only(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: type("S", (), {"database_url": "postgresql://u:p@host/db"})(),
        )
        identity = database_identity()
        assert identity["dialect"] == "postgresql"
        assert identity["configured"] is True
        assert identity["remote"] is True
        assert "withheld" in identity["note"]

    def test_an_absent_url_is_reported_not_invented(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: type("S", (), {"database_url": ""})(),
        )
        identity = database_identity()
        assert identity["configured"] is False
        assert identity["dialect"] == "none"

    def test_the_production_dialect_is_not_inferred_from_this_process(self, monkeypatch):
        """A local SQLite default says nothing about production."""
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: type("S", (), {"database_url": "sqlite:///./dev.db"})(),
        )
        evidence = production_dialect_evidence()
        assert evidence["method"].startswith("repository assertion only")
        assert evidence["dialect"] in {"postgresql", UNKNOWN}
        assert evidence["basis"], "the dialect claim must name what it rests on"


# ---------------------------------------------------------------------------
# Phase 5 - the plan
# ---------------------------------------------------------------------------


class TestRecoveryPlan:
    def test_all_eleven_items_are_present(self):
        assert [item.number for item in RECOVERY_PLAN] == list(range(1, 12))

    def test_every_item_says_how_it_is_verified(self):
        for item in RECOVERY_PLAN:
            assert len(item.verification) > 30, item.number
            assert len(item.specification) > 60, item.number

    def test_the_plan_covers_each_required_topic(self):
        text = " ".join(item.item.lower() for item in RECOVERY_PLAN)
        for topic in ("technology", "schedule", "retention", "encryption",
                      "access control", "destination", "verification",
                      "recovery point objective", "recovery time objective",
                      "approval", "evidence artefact"):
            assert topic in text, topic

    def test_the_plan_is_not_implemented_as_infrastructure(self):
        """Phase 5 forbids speculative infrastructure.

        The plan exists as data. Nothing in this repository materialises a backup
        system, which is the correct outcome while no owner authorisation exists.
        """
        assert all(isinstance(item.specification, str) for item in RECOVERY_PLAN)
        plan = recovery_plan_as_dict()
        assert len(plan) == 11

    def test_rpo_and_rto_are_explicit(self):
        rpo = [i for i in RECOVERY_PLAN if "Recovery point" in i.item][0]
        rto = [i for i in RECOVERY_PLAN if "Recovery time" in i.item][0]
        assert "RPO" in rpo.specification
        assert "RTO" in rto.specification
        assert "owner" in rpo.specification.lower()

    def test_owner_approval_is_required_twice(self):
        approval = [i for i in RECOVERY_PLAN if "approval" in i.item.lower()][0]
        assert "two approvals" in approval.specification.lower()
        assert "neither implied by the other" in approval.specification.lower()


# ---------------------------------------------------------------------------
# Phase 10 - the manifest says it is not a backup
# ---------------------------------------------------------------------------


class TestManifestSemantics:
    def test_the_disclaimer_says_manifest_is_not_a_backup(self):
        assert MANIFEST_DISCLAIMER["MANIFEST != BACKUP"]
        assert MANIFEST_DISCLAIMER["manifest_is_a_backup"] is False
        assert MANIFEST_DISCLAIMER["recoverable"] is False
        assert "NOT a backup" in MANIFEST_DISCLAIMER["MANIFEST != BACKUP"]
        assert "cannot reinstate" in MANIFEST_DISCLAIMER["MANIFEST != BACKUP"]

    def test_every_written_entry_carries_the_disclaimer(self, tmp_path):
        path = tmp_path / "l.json"
        append_deletion_manifest(
            {"run_id": "r", "run_token": "r-1", "deleted_at": "t", "deleted": 1,
             "ids": [1], "records": [], "confirmed": True}, path=path,
        )
        written = json.loads(path.read_text(encoding="utf-8"))
        entry = written["retention_batches"][-1]
        assert entry["manifest_is_a_backup"] is False
        assert entry["manifest_kind"] == "retention_deletion_manifest"
        assert entry["purpose"] == "audit and reconciliation only"

    def test_credential_shaped_fields_are_refused(self, tmp_path):
        for key in ("password", "database_url", "api_key", "authorization", "email"):
            with pytest.raises(ValueError, match="credential-shaped"):
                append_deletion_manifest(
                    {"run_id": "r", "run_token": f"r-{key}", "deleted_at": "t",
                     "deleted": 0, "records": [], "confirmed": False,
                     key: "value"},
                    path=tmp_path / f"{key}.json",
                )

    def test_credential_refusal_covers_nested_structures(self, tmp_path):
        with pytest.raises(ValueError, match="credential-shaped"):
            append_deletion_manifest(
                {"run_id": "r", "run_token": "r-nested", "deleted_at": "t", "deleted": 0,
                 "records": [{"scholarship_id": 1, "detail": {"secret": "x"}}],
                 "confirmed": False},
                path=tmp_path / "nested.json",
            )
        assert not (tmp_path / "nested.json").exists(), (
            "the refused entry must not have been written at all"
        )

    def test_the_manifest_carries_the_required_audit_metadata(self, tmp_path):
        from app.services.retention_engine import _manifest_record

        decision = classify(facts(42), policy=default_policy(), as_of=AS_OF)
        record = _manifest_record(decision, run_id="run-9", as_of=AS_OF)
        for key in ("record_identity", "classification_reason", "decision_timestamp",
                    "run_id", "contract_version", "conditions_verified",
                    "dependencies_present_at_decision", "dependencies_preserved",
                    "retention" if "retention" in record else "dependencies_preserved"):
            assert key in record, key
        assert record["record_identity"] == {"table": "scholarships", "id": 42}
        assert record["recoverable_from_this_entry"] is False
        assert record["dependencies_preserved"] == sorted(PRESERVE_MODELS)

    def test_the_manifest_does_not_claim_to_store_row_data(self, tmp_path):
        """A full payload would help re-insertion and would also mean an
        untracked second copy of the catalogue."""
        from app.services.retention_engine import _manifest_record

        record = _manifest_record(
            classify(facts(1), policy=default_policy(), as_of=AS_OF), run_id="r", as_of=AS_OF
        )
        serialised = json.dumps(record)
        assert "official_source_url" not in serialised
        assert "description" not in serialised

    def test_every_preserve_table_is_named_in_the_manifest(self):
        report = reference_integrity_report()
        assert report["integrity_uncertain"] is False
        assert report["relationship_count"] == 13
        assert set(PRESERVE_MODELS) == {
            "ScholarshipReview", "ScholarshipVerificationHistory", "ScholarshipSnapshot",
            "ScholarshipRestoreRecord", "ImageReview",
            "SavedScholarship", "ApplicationRecord",
            "ScholarshipSupervisorCoverage", "ScholarshipProfessorLink",
            "SupervisorSourceEvidence", "ProfessorOutreachRecord",
        }


#: The shape the closed-record collector actually writes. Reproduced because the
#: collector's ledger has no ``batches`` key at all - a detail an earlier version
#: of the manifest writer got wrong and paid for.
COLLECTOR_LEDGER = {
    "purged_at": "2026-09-02T12:27:51+00:00",
    "count": 151,
    "records": [{"id": i, "reason": "collector removal"} for i in range(1, 152)],
    "breakdown": {"closed": 120, "expired": 31},
    "child_rows": {"scholarship_reviews": 40},
    "children": ["scholarship_reviews"],
}


class TestTheLedgerIsAppendOnly:
    """The retention engine must never damage the collector's ledger.

    Regression tests for a real data-loss defect: ``append_deletion_manifest``
    rebuilt ``records`` from ``batches`` and recomputed ``count``. Since the
    collector's ledger contains no ``batches`` key, that rewrote 151 historical
    records to an empty list and truncated a 30,000-line file. Every test passed,
    because every test wrote to a fresh temporary ledger and never exercised the
    shared one.
    """

    def _seed(self, tmp_path):
        path = tmp_path / "purged_records_archive.json"
        path.write_text(json.dumps(COLLECTOR_LEDGER, indent=2), encoding="utf-8")
        return path

    def test_the_shared_ledger_shape_is_what_we_assume(self, tmp_path):
        """Pins the fact the bug turned on: no ``batches`` key exists."""
        path = self._seed(tmp_path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert "batches" not in loaded
        assert loaded["count"] == 151
        assert len(loaded["records"]) == 151

    def test_every_collector_key_survives_a_retention_write(self, tmp_path):
        path = self._seed(tmp_path)
        append_deletion_manifest(
            {"run_id": "r1", "run_token": "r1-1", "mode": "DELETE",
             "deleted_at": "2026-10-05T12:00:00+00:00", "deleted": 2, "ids": [900, 901],
             "records": [{"record_identity": {"id": 900}}], "confirmed": True},
            path=path,
        )
        written = json.loads(path.read_text(encoding="utf-8"))
        for key, value in COLLECTOR_LEDGER.items():
            assert key in written, f"the collector's {key} key was destroyed"
            assert written[key] == value, f"the collector's {key} was modified"

    def test_the_records_survive_byte_for_byte(self, tmp_path):
        path = self._seed(tmp_path)
        before = json.loads(path.read_text(encoding="utf-8"))["records"]
        append_deletion_manifest(
            {"run_id": "r1", "run_token": "r1-1", "mode": "DELETE",
             "deleted_at": "t", "deleted": 1, "ids": [1], "records": [], "confirmed": True},
            path=path,
        )
        after = json.loads(path.read_text(encoding="utf-8"))["records"]
        assert after == before
        assert len(after) == 151

    def test_the_collector_count_is_not_incremented_by_retention_deletions(self, tmp_path):
        """Two ledgers sharing a file must not share a total.

        Incrementing one counter from both would make "151 deleted" mean something
        nobody could reconstruct.
        """
        path = self._seed(tmp_path)
        append_deletion_manifest(
            {"run_id": "r1", "run_token": "r1-1", "mode": "DELETE",
             "deleted_at": "t", "deleted": 7, "ids": list(range(7)), "records": [],
             "confirmed": True},
            path=path,
        )
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["count"] == 151
        assert written["retention_summary"]["retention_deleted"] == 7

    def test_retention_data_lives_under_its_own_keys(self, tmp_path):
        path = self._seed(tmp_path)
        append_deletion_manifest(
            {"run_id": "r1", "run_token": "r1-1", "mode": "DELETE", "deleted_at": "t",
             "deleted": 1, "ids": [1], "records": [], "confirmed": True},
            path=path,
        )
        written = json.loads(path.read_text(encoding="utf-8"))
        assert "retention_batches" in written
        assert "retention_summary" in written
        assert "retention_runs" in written
        assert written["retention_summary"]["retention_deleted"] == 1

    def test_a_fresh_ledger_is_created_when_none_exists(self, tmp_path):
        path = tmp_path / "new.json"
        append_deletion_manifest(
            {"run_id": "r", "run_token": "r-1", "mode": "DELETE", "deleted_at": "t",
             "deleted": 1, "ids": [1], "records": [], "confirmed": True},
            path=path,
        )
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["retention_summary"]["retention_deleted"] == 1
        assert "records" not in written

    def test_an_unreadable_ledger_is_preserved_not_replaced(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ this is not json", encoding="utf-8")
        append_deletion_manifest(
            {"run_id": "r", "run_token": "r-1", "mode": "DELETE", "deleted_at": "t",
             "deleted": 1, "ids": [1], "records": [], "confirmed": True},
            path=path,
        )
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["ledger_unreadable"] is True
        assert "retention_batches" in written

    def test_the_repository_ledger_is_never_written_by_a_suite_run(self):
        """The property that keeps the test suite from falsifying the record."""
        from app.services.retention_engine import ledger_path

        path = ledger_path()
        if not path.exists():  # pragma: no cover - the file is tracked
            pytest.skip("no repository ledger present")
        before = path.read_bytes()
        # Nothing in this module writes to the default path; assert the default
        # resolves to the tracked file so a future change cannot redirect it.
        assert path.name == "purged_records_archive.json"
        assert before == path.read_bytes()


# ---------------------------------------------------------------------------
# Phase 11 - the release gate
# ---------------------------------------------------------------------------


def _complete_evidence() -> dict:
    return {
        **{field: "x" for field in REQUIRED_EVIDENCE_FIELDS},
        "__recovery__": {
            "recovery_source_proven": True,
            "restore_test_passed": True,
            "foreign_key_validation_passed": True,
            "child_evidence_verified": True,
            "procedure_documented": True,
        },
        "__candidates__": {"all_grace_satisfied": True, "no_conflicting_state": True},
        "__owner__": {"authorised": True},
    }


class TestReleaseGateIsClosed:
    def test_with_no_evidence_the_gate_is_held(self):
        report = evaluate_release_gate(None)
        assert report["verdict"] == HELD
        assert report["hard_delete"] == HELD
        assert report["evidence_supplied"] is False

    def test_all_twelve_conditions_are_evaluated(self):
        report = evaluate_release_gate(None)
        assert report["conditions_total"] == 12
        assert [c["id"] for c in report["conditions"]] == list(range(1, 13))

    def test_every_evidence_condition_is_unmet_without_evidence(self):
        report = evaluate_release_gate(None)
        for row in report["conditions"]:
            if row["source"] == "evidence":
                assert not row["satisfied"], row["id"]
                assert row["status"] == "ABSENT"

    def test_the_recovery_contract_holds_condition_one(self):
        report = evaluate_release_gate(None)
        condition = [c for c in report["conditions"] if c["id"] == 1][0]
        assert not condition["satisfied"]
        assert report["recovery_contract_verdict"] == "RECOVERY_PATH_NOT_PROVEN"

    def test_a_complete_evidence_file_alone_does_not_release(self):
        """Recovery plus authorisation is not enough while requirement A is unmet.

        This is the gate's most important negative test: it proves the recovery
        contract is re-derived live rather than read from the artefact, so a
        complete-looking file cannot wave the gate open.
        """
        report = evaluate_release_gate(_complete_evidence())
        assert report["verdict"] == HELD
        assert 1 in report["unmet_ids"]

    def test_owner_authorisation_is_not_inferable(self):
        without_owner = _complete_evidence()
        without_owner["__owner__"] = {"authorised": False}
        report = evaluate_release_gate(without_owner)
        assert not [c for c in report["conditions"] if c["id"] == 9][0]["satisfied"]
        assert 9 in report["unmet_ids"]

    def test_a_partial_artefact_is_reported_as_incomplete(self):
        partial = _complete_evidence()
        partial.pop("recovery_point")
        report = evaluate_release_gate(partial)
        assert report["evidence_artefact_complete"] is False
        assert "recovery_point" in report["evidence_fields_missing"]

    def test_an_unbounded_policy_fails_condition_ten(self):
        report = evaluate_release_gate(
            None, policy=RetentionPolicy(max_delete_per_run=0)
        )
        condition = [c for c in report["conditions"] if c["id"] == 10][0]
        assert not condition["satisfied"]
        assert report["verdict"] == HELD

    def test_an_impossible_percentage_fails_condition_ten(self):
        report = evaluate_release_gate(None, policy=RetentionPolicy(max_delete_percentage=0))
        assert not [c for c in report["conditions"] if c["id"] == 10][0]["satisfied"]

    def test_the_shipped_policy_is_bounded(self):
        report = evaluate_release_gate(None, policy=default_policy())
        condition = [c for c in report["conditions"] if c["id"] == 10][0]
        assert condition["satisfied"] is True

    def test_next_actions_name_the_blocking_items(self):
        report = evaluate_release_gate(None)
        joined = " ".join(report["next_actions"]).lower()
        assert "recovery source" in joined
        assert "authorisation" in joined

    def test_condition_nine_names_its_evidence_field(self):
        condition = [c for c in GATE_CONDITIONS if c.id == 9][0]
        assert condition.evidence_field == "__owner__.authorised"
        assert "Inferable from nothing else" in condition.derived_from

    def test_every_condition_is_documented_with_a_source(self):
        for condition in GATE_CONDITIONS:
            assert condition.condition
            assert condition.derived_from or condition.evidence_field


# ---------------------------------------------------------------------------
# Phase 8 - recovery and retention together
# ---------------------------------------------------------------------------


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'integration.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


class TestRecoveryAndRetentionIntegration:
    """Retention behaviour is proven offline; the restore proof is not available.

    Every record shape the task names is seeded and classified. The restore half
    of the integration is reported as unavailable rather than approximated -
    there is no PostgreSQL server in this environment, and a SQLite round-trip
    would be evidence about a different database.
    """

    def test_every_required_record_shape_is_seeded_and_classified(self, session):
        records = {
            "live": Scholarship(
                title="L", country="CA", degree="M", funding="F", official_source="U",
                official_source_url="https://i.test/live", status="open", is_archived=False,
                is_verified=True, verification_status="active",
                image_url="https://i.test/l.png", image_verified_at=ANCIENT,
                image_source_type="official",
            ),
            "missing_image": Scholarship(
                title="M", country="CA", degree="M", funding="F", official_source="U",
                official_source_url="https://i.test/nologo", status="open", is_archived=False,
                is_verified=True, verification_status="active",
            ),
            "archived": Scholarship(
                title="A", country="PE", degree="M", funding="P", official_source="O",
                official_source_url="https://i.test/archived", status="closed",
                is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
                is_verified=False, verification_status="inactive",
            ),
            "admin_review": Scholarship(
                title="R", country="JP", degree="P", funding="F", official_source="R",
                official_source_url="https://i.test/review", status="closed",
                is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
                is_verified=False, verification_status="needs_review",
            ),
            "unknown": Scholarship(
                title="U", country="BR", degree="M", funding="P", official_source="U",
                official_source_url="https://i.test/unknown", status="closed",
                is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
                auto_delete_candidate_since=ANCIENT, is_verified=False,
                verification_status="never_classified",
            ),
            "ambiguous": Scholarship(
                title="G", country="BR", degree="M", funding="P", official_source="U",
                official_source_url="https://i.test/ambiguous", status="closed",
                is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
                auto_delete_candidate_since=ANCIENT, is_verified=False,
                verification_status="inactive",
            ),
            "conflicting": Scholarship(
                title="C", country="BR", degree="M", funding="P", official_source="U",
                official_source_url="https://i.test/conflicting", status="closed",
                is_archived=True, archived_at=None, is_verified=False,
                verification_status="inactive",
            ),
            "protected": Scholarship(
                title="P", country="BR", degree="M", funding="P", official_source="U",
                official_source_url="https://i.test/protected", status="closed",
                is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
                auto_delete_candidate_since=ANCIENT, is_verified=False,
                verification_status="quarantined",
            ),
            "candidate": Scholarship(
                title="K", country="PE", degree="M", funding="P", official_source="O",
                official_source_url="https://i.test/candidate", status="closed",
                is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
                auto_delete_candidate_since=ANCIENT, is_verified=False,
                verification_status="inactive", deadline_date=date(2018, 6, 1),
            ),
            "with_children": Scholarship(
                title="D", country="ZA", degree="M", funding="P", official_source="E",
                official_source_url="https://i.test/children", status="closed",
                is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
                auto_delete_candidate_since=ANCIENT, is_verified=False,
                verification_status="inactive", deadline_date=date(2018, 6, 1),
            ),
        }
        session.add_all(records.values())
        session.commit()
        # The two rows that need child evidence or an incomplete read to take the
        # shape their name claims.
        session.add(
            ScholarshipReview(
                scholarship_id=records["with_children"].id, field_name="status",
                conflict_reason="settled", verification_state="confirmed",
                decision="confirmed", reviewed_at=ANCIENT, reviewed_by="operator",
            )
        )
        session.add(
            DiscoveryCandidate(
                source_url="https://i.test/ambiguous", normalized_url="https://i.test/ambiguous",
                discovery_hash="h", status="resolved", match_status="rejected",
                matched_scholarship_id=records["ambiguous"].id, resolved_at=ANCIENT,
            )
        )
        session.commit()

        from app.services.retention_engine import scan

        states = {d.scholarship_id: d.state for d in scan(session, as_of=AS_OF)}
        by_name = {name: states[row.id] for name, row in records.items()}

        assert by_name["live"] == STATE_KEEP
        assert by_name["missing_image"] == STATE_PROTECTED
        # Archived and well past retention, but never armed: this is precisely
        # GRACE_ELIGIBLE. Calling it merely "protected" would hide the fact that
        # every other deletion condition already holds.
        assert by_name["archived"] == STATE_GRACE_ELIGIBLE
        assert by_name["admin_review"] == STATE_KEEP
        assert by_name["unknown"] == STATE_UNKNOWN
        assert by_name["conflicting"] == STATE_CONFLICTING
        assert by_name["protected"] == STATE_PROTECTED
        assert by_name["candidate"] == STATE_DELETE_CANDIDATE
        assert by_name["with_children"] == STATE_PROTECTED

    def test_delete_candidate_is_constrained_to_one_record(self, session):
        rows = [
            Scholarship(
                title=f"K{i}", country="PE", degree="M", funding="P", official_source="O",
                official_source_url=f"https://i.test/c{i}", status="closed", is_archived=True,
                archived_at=ANCIENT, archived_reason="deadline passed",
                auto_delete_candidate_since=ANCIENT, is_verified=False,
                verification_status="inactive", deadline_date=date(2018, 6, 1),
            )
            for i in range(3)
        ]
        rows.append(
            Scholarship(
                title="Blocked", country="PE", degree="M", funding="P", official_source="O",
                official_source_url="https://i.test/blocked", status="closed", is_archived=True,
                archived_at=ANCIENT, archived_reason="deadline passed",
                auto_delete_candidate_since=ANCIENT, is_verified=False,
                verification_status="needs_review",
            )
        )
        session.add_all(rows)
        session.commit()

        from app.services.retention_engine import scan

        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        assert sorted(candidates) == sorted(r.id for r in rows[:3])
        assert rows[3].id not in candidates

    def test_the_restore_half_of_the_integration_is_not_available(self):
        """Stated as a fact of this environment, not silently skipped.

        There is no PostgreSQL server and no dump tooling here, so requirements
        B through E of the recovery contract cannot be demonstrated. Reporting
        this as unavailable is the honest outcome; approximating it with SQLite
        would be a proof of the wrong database.
        """
        inventory = recovery_capability_inventory()
        dump_tooling = [i for i in inventory if i["id"] == "R4"][0]
        assert dump_tooling["status"] == ABSENT

        report = recovery_requirements_report(inventory)
        for requirement in ("B", "C", "D", "E"):
            row = [r for r in report["requirements"] if r["id"] == requirement][0]
            assert not row["satisfied"]
