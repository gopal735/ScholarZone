"""Phase 19 - the invariants, and Phase 15/16 - the visible consequence.

Two kinds of test live here.

The property suite generates whole populations from a fixed seed and asserts the
safety invariants over each one. A fixed seed rather than a random one is
deliberate: a failure in a destructive-safety suite has to be reproducible
exactly, and a generator that re-rolls turns "this invariant is violated" into
"this invariant is violated sometimes, good luck". The generator explores the
combinations that matter - every verification status including ones nobody has
classified, every lifecycle status, both clock states, present and absent
dependencies - and every one of them is checked against the same four claims.

The visibility suite proves the consequence the whole design exists to protect:
a record under admin review is still stored, still findable by an administrator,
and still absent from the public catalogue.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, or_, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    ImageReview,
    Scholarship,
    ScholarshipReview,
)
from app.repositories.scholarships import list_scholarships, public_visibility_conditions
from app.schemas import ScholarshipQuery
from app.services.counting.catalogue import catalogue_counts
from app.services.retention_contract import (
    ADMIN_REVIEW_STATUSES,
    BUCKET_ADMIN_REVIEW,
    BUCKET_AMBIGUOUS,
    BUCKET_CONFLICTING,
    BUCKET_LIVE,
    BUCKET_PROTECTED,
    RECOGNISED_LIFECYCLE_STATUSES,
    RECOGNISED_VERIFICATION_STATUSES,
    RetentionFacts,
    RetentionPolicy,
    assert_invariants,
    classify,
    default_policy,
    summarise,
)
from app.services.retention_engine import (
    admin_review_conditions,
    delete_bounded,
    dry_run,
    scan,
)

AS_OF = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
ANCIENT = datetime(2019, 1, 1, tzinfo=timezone.utc)

#: A fixed seed. Every property run is reproducible from this number.
SEED = 20261005

#: States the repository has never classified, deliberately included so the
#: generated populations always contain something the engine has no answer for.
UNRECOGNISED_VERIFICATIONS = ("mystery", "", "   ", None, "PENDING_REVIEW", "Active")
UNRECOGNISED_LIFECYCLES = ("rolling", "", None, "OPEN", "expired")

DELETING = RetentionPolicy(
    cleanup_enabled=True, dry_run=False, batch_size=8, max_delete_percentage=1.0
)


@pytest.fixture(autouse=True)
def production_visibility_gate(monkeypatch):
    """Run under the production visibility contract, not the suite-wide one.

    ``tests/conftest.py`` disables both public quality gates for the legacy
    listing fixtures. A property suite over a population that cannot express "not
    live because it has no verified image" would be testing a catalogue that does
    not exist in production.
    """
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE", "false")


def generate_facts(rng: random.Random, count: int) -> list[RetentionFacts]:
    """A population spanning every state the classifier can encounter."""
    population: list[RetentionFacts] = []
    for index in range(count):
        verification = rng.choice(
            sorted(RECOGNISED_VERIFICATION_STATUSES) + list(UNRECOGNISED_VERIFICATIONS)
        )
        lifecycle = rng.choice(
            list(RECOGNISED_LIFECYCLE_STATUSES) + list(UNRECOGNISED_LIFECYCLES)
        )
        archived = rng.choice([True, False])
        has_clock = rng.choice([True, True, False])
        armed = rng.choice([True, True, False])
        population.append(
            RetentionFacts(
                scholarship_id=index,
                # A quarter of the population is live, drawn from the states the
                # catalogue actually lists.
                is_live=rng.random() < 0.25,
                pending_scholarship_reviews=rng.choice([0, 0, 0, 1, 2]),
                pending_image_reviews=rng.choice([0, 0, 0, 0, 1]),
                verification_status=verification,
                lifecycle_status=lifecycle,
                deletion_protected=rng.random() < 0.1,
                is_archived=archived,
                archived_at=ANCIENT if has_clock else None,
                archived_reason=rng.choice([None, "", "deadline passed on 2019-01-01"]),
                candidate_since=ANCIENT if armed else None,
                is_verified=rng.choice([True, False]),
                deadline_date=date(2018, 6, 1),
                blocking_dependencies=rng.choice(
                    [frozenset(), frozenset(), frozenset({"ScholarshipSnapshot"})]
                ),
                evidence_complete=rng.random() > 0.05,
                evidence_error=None,
            )
        )
    return population


# ---------------------------------------------------------------------------
# Phase 19 - properties over generated populations
# ---------------------------------------------------------------------------


class TestPropertiesOverGeneratedPopulations:
    @pytest.mark.parametrize("population_size", [1, 5, 25, 200])
    def test_no_record_is_ever_in_two_buckets_at_once(self, population_size):
        rng = random.Random(SEED + population_size)
        decisions = [
            classify(f, policy=default_policy(), as_of=AS_OF) for f in generate_facts(rng, population_size)
        ]
        ids = [d.scholarship_id for d in decisions]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("population_size", [1, 5, 25, 200])
    def test_the_four_claims_hold_over_the_population(self, population_size):
        """KEEP = LIVE ∪ ADMIN_REVIEW, and the three disjointness claims."""
        rng = random.Random(SEED + population_size)
        decisions = [
            classify(f, policy=default_policy(), as_of=AS_OF) for f in generate_facts(rng, population_size)
        ]

        live = {d.scholarship_id for d in decisions if d.bucket == BUCKET_LIVE}
        review = {d.scholarship_id for d in decisions if d.bucket == BUCKET_ADMIN_REVIEW}
        keep = {d.scholarship_id for d in decisions if d.is_keep}
        delete = {d.scholarship_id for d in decisions if d.is_delete}
        unclassified = {
            d.scholarship_id
            for d in decisions
            if d.bucket in {BUCKET_AMBIGUOUS, BUCKET_CONFLICTING}
        }

        # LIVE ∩ DELETE = ∅
        assert live & delete == set()
        # ADMIN_REVIEW ∩ DELETE = ∅
        assert review & delete == set()
        # DELETE ∩ KEEP = ∅
        assert delete & keep == set()
        # No ambiguous or conflicting record can be deleted.
        assert unclassified & delete == set()
        # KEEP ⊇ LIVE ∪ ADMIN_REVIEW
        assert keep >= live | review
        # And nothing is deletable outside the "neither live nor review" set.
        assert delete == {d.scholarship_id for d in decisions if d.bucket not in
                          {BUCKET_LIVE, BUCKET_ADMIN_REVIEW, BUCKET_PROTECTED,
                           BUCKET_AMBIGUOUS, BUCKET_CONFLICTING}}

    @pytest.mark.parametrize("population_size", [5, 25, 200])
    def test_the_assertion_holds_over_the_population(self, population_size):
        rng = random.Random(SEED + population_size)
        decisions = [
            classify(f, policy=default_policy(), as_of=AS_OF) for f in generate_facts(rng, population_size)
        ]
        assert_invariants(decisions)

    @pytest.mark.parametrize("population_size", [5, 25, 200])
    def test_the_summary_reconciles_over_the_population(self, population_size):
        rng = random.Random(SEED + population_size)
        decisions = [
            classify(f, policy=default_policy(), as_of=AS_OF) for f in generate_facts(rng, population_size)
        ]
        summary = summarise(decisions)
        assert summary.reconciles()
        assert summary.scanned == population_size

    @pytest.mark.parametrize("population_size", [5, 25, 200])
    def test_no_delete_ever_carries_a_failing_check(self, population_size):
        rng = random.Random(SEED + population_size)
        decisions = [
            classify(f, policy=default_policy(), as_of=AS_OF) for f in generate_facts(rng, population_size)
        ]
        for decision in decisions:
            if decision.is_delete:
                failing = sorted(k for k, ok in decision.checks.items() if not ok)
                assert failing == [], f"{decision.scholarship_id}: {failing}"

    @pytest.mark.parametrize("population_size", [5, 25])
    def test_classification_is_deterministic(self, population_size):
        rng = random.Random(SEED + population_size)
        facts = generate_facts(rng, population_size)
        first = [classify(f, policy=default_policy(), as_of=AS_OF).as_dict() for f in facts]
        second = [classify(f, policy=default_policy(), as_of=AS_OF).as_dict() for f in facts]
        assert first == second

    def test_an_unrecognised_status_is_never_deletable(self):
        """Phase 4, over the whole space of unrecognised values."""
        for value in UNRECOGNISED_VERIFICATIONS:
            decision = classify(
                RetentionFacts(
                    scholarship_id=1, is_live=False, verification_status=value,
                    lifecycle_status="closed", is_archived=True, archived_at=ANCIENT,
                    archived_reason="deadline passed on 2019-01-01",
                    candidate_since=ANCIENT, is_verified=False,
                    deadline_date=date(2018, 6, 1),
                ),
                policy=default_policy(), as_of=AS_OF,
            )
            assert decision.is_keep, f"verification_status={value!r} was deletable"
            assert decision.bucket == BUCKET_AMBIGUOUS, (
                f"verification_status={value!r} landed in {decision.bucket}"
            )

    def test_an_unrecognised_lifecycle_status_is_never_deletable(self):
        for value in UNRECOGNISED_LIFECYCLES:
            decision = classify(
                RetentionFacts(
                    scholarship_id=1, is_live=False, verification_status="inactive",
                    lifecycle_status=value, is_archived=True, archived_at=ANCIENT,
                    archived_reason="deadline passed on 2019-01-01",
                    candidate_since=ANCIENT, is_verified=False,
                    deadline_date=date(2018, 6, 1),
                ),
                policy=default_policy(), as_of=AS_OF,
            )
            assert decision.is_keep, f"status={value!r} was deletable"
            assert decision.bucket in {BUCKET_AMBIGUOUS, BUCKET_LIVE, BUCKET_ADMIN_REVIEW}

    def test_admin_review_always_beats_a_deletable_shape(self):
        for status in sorted(ADMIN_REVIEW_STATUSES):
            decision = classify(
                RetentionFacts(
                    scholarship_id=1, is_live=False, verification_status=status,
                    lifecycle_status="closed", is_archived=True, archived_at=ANCIENT,
                    candidate_since=ANCIENT, is_verified=False,
                ),
                policy=default_policy(), as_of=AS_OF,
            )
            assert decision.bucket == BUCKET_ADMIN_REVIEW, status
            assert not decision.is_delete, status

    def test_a_whole_population_of_deletable_records_still_needs_an_enabled_policy(self):
        """Nothing about a large candidate set grants permission to delete."""
        facts = [
            RetentionFacts(
                scholarship_id=i, is_live=False, verification_status="inactive",
                lifecycle_status="closed", is_archived=True, archived_at=ANCIENT,
                archived_reason="deadline passed", candidate_since=ANCIENT,
            )
            for i in range(100)
        ]
        decisions = [classify(f, policy=default_policy(), as_of=AS_OF) for f in facts]
        assert all(d.is_delete for d in decisions)
        with pytest.raises(PermissionError):
            default_policy().assert_deletion_permitted()


# ---------------------------------------------------------------------------
# Phase 9/19 - transitions from candidate to protected, against a database
# ---------------------------------------------------------------------------


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'invariants.db'}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


def make_candidate(session, index: int) -> int:
    row = Scholarship(
        title=f"Candidate {index}",
        country="Peru",
        degree="Master",
        funding="Partial",
        official_source="Old Institute",
        official_source_url=f"https://old.test/c{index}",
        status="closed",
        is_archived=True,
        archived_at=ANCIENT,
        archived_reason="deadline passed on 2019-01-01",
        auto_delete_candidate_since=ANCIENT,
        is_verified=False,
        verification_status="inactive",
        deadline_date=date(2018, 6, 1),
    )
    session.add(row)
    session.commit()
    return row.id


def stored(session, scholarship_id: int) -> bool:
    session.expire_all()
    return session.scalar(select(Scholarship.id).where(Scholarship.id == scholarship_id)) is not None


@pytest.fixture()
def tmp_ledger(tmp_path) -> Path:
    """Where a deleting test writes its manifest.

    The engine's default ledger is a tracked file in the repository. A test that
    deletes anything without redirecting it appends a permanent, false entry to
    the project's record of what has been deleted.
    """
    return tmp_path / "purged_records_archive.json"


class TestCandidateTransitions:
    def test_candidate_to_live_ends_in_keep(self, session, tmp_ledger):
        """Phase 19: DELETE_CANDIDATE -> LIVE before the delete means KEEP."""
        row_id = make_candidate(session, 1)
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        assert candidates == [row_id]

        row = session.get(Scholarship, row_id)
        row.is_archived = False
        row.archived_at = None
        row.status = "open"
        row.is_verified = True
        row.verification_status = "active"
        row.image_url = "https://old.test/logo.png"
        row.image_verified_at = ANCIENT
        row.image_source_type = "official"
        row.deadline_date = date(2099, 1, 1)
        session.commit()

        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="t-lc")
        assert report["deleted"] == []
        assert stored(session, row_id) is True
        decision = next(d for d in scan(session, as_of=AS_OF) if d.scholarship_id == row_id)
        assert decision.bucket == BUCKET_LIVE

    def test_candidate_to_admin_review_ends_in_keep(self, session, tmp_ledger):
        """Phase 19: DELETE_CANDIDATE -> ADMIN_REVIEW before the delete means KEEP."""
        row_id = make_candidate(session, 2)
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        assert candidates == [row_id]

        session.add(
            ScholarshipReview(
                scholarship_id=row_id, field_name="status",
                conflict_reason="an operator opened a review",
                verification_state="needs_review", decision="pending",
            )
        )
        session.commit()

        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="t-ar")
        assert report["deleted"] == []
        assert stored(session, row_id) is True
        decision = next(d for d in scan(session, as_of=AS_OF) if d.scholarship_id == row_id)
        assert decision.bucket == BUCKET_ADMIN_REVIEW

    def test_candidate_to_ambiguous_ends_in_keep(self, session, tmp_ledger):
        row_id = make_candidate(session, 3)
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        session.get(Scholarship, row_id).verification_status = "some-new-state"
        session.commit()
        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="t-am")
        assert report["deleted"] == []
        assert stored(session, row_id) is True

    def test_candidate_to_conflicting_ends_in_keep(self, session, tmp_ledger):
        row_id = make_candidate(session, 4)
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        session.get(Scholarship, row_id).archived_reason = None
        session.commit()
        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="t-cf")
        assert report["deleted"] == []
        assert stored(session, row_id) is True

    def test_a_stable_candidate_is_still_deleted(self, session, tmp_ledger):
        """The control case: without a transition, a proven candidate goes.

        Without this, the four tests above would also pass against an engine that
        never deletes anything.
        """
        row_id = make_candidate(session, 5)
        report = delete_bounded(session, [row_id], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="t-ok")
        assert report["deleted"] == [row_id]
        assert stored(session, row_id) is False

    def test_a_failing_statement_deletes_nothing_at_all(self, session, tmp_ledger):
        """Phase 13: no partial "best effort" cleanup.

        The failure is injected at the database rather than at ``Session.commit``,
        because a commit that raises before doing anything is not how a real
        transaction fails - a real one fails with the statements already sent, and
        the guarantee being tested is that the rollback undoes them.
        """
        rows = [make_candidate(session, 100 + i) for i in range(4)]
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        assert candidates == rows

        @event.listens_for(session.get_bind(), "before_cursor_execute")
        def _fail_scholarship_delete(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("DELETE FROM SCHOLARSHIPS"):
                raise RuntimeError("simulated database failure on the delete")

        try:
            report = delete_bounded(
                session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="t-tx"
            )
        finally:
            event.remove(session.get_bind(), "before_cursor_execute", _fail_scholarship_delete)

        assert all(stored(session, rid) is True for rid in rows), (
            "a failed statement must leave every record in place"
        )
        assert report["deleted"] == []
        assert any("transaction rolled back" in a["reason"] for a in report["aborted"])


# ---------------------------------------------------------------------------
# Phase 15/16 - what the public and the admin each see
# ---------------------------------------------------------------------------


def seed_mixed(session) -> dict[str, int]:
    """One record per visibility outcome, so each claim has a subject."""
    rows: dict[str, int] = {}

    live = Scholarship(
        title="Listed Programme", country="Canada", degree="Master", funding="Full",
        official_source="Example University", official_source_url="https://example.test/listed",
        status="open", is_archived=False, is_verified=True, verification_status="active",
        image_url="https://example.test/logo.png", image_verified_at=ANCIENT,
        image_source_type="official",
    )
    no_logo = Scholarship(
        title="Unlisted Programme", country="Canada", degree="Master", funding="Full",
        official_source="Quiet University", official_source_url="https://example.test/unlisted",
        status="open", is_archived=False, is_verified=True, verification_status="active",
    )
    archived = Scholarship(
        title="Closed Programme", country="Peru", degree="Master", funding="Partial",
        official_source="Old Institute", official_source_url="https://old.test/closed",
        status="closed", is_archived=True, archived_at=ANCIENT,
        archived_reason="deadline passed on 2019-01-01",
        is_verified=False, verification_status="inactive",
    )
    under_review = Scholarship(
        title="Under Review Programme", country="Japan", degree="PhD", funding="Full",
        official_source="Review Institute", official_source_url="https://review.test/x",
        status="closed", is_archived=True, archived_at=ANCIENT,
        archived_reason="deadline passed on 2019-01-01",
        is_verified=False, verification_status="needs_review",
    )
    session.add_all([live, no_logo, archived, under_review])
    session.commit()
    rows.update(live=live.id, no_logo=no_logo.id, archived=archived.id, review=under_review.id)
    return rows


class TestPublicCatalogueEffect:
    def test_the_directory_lists_exactly_the_live_record(self, session):
        ids = seed_mixed(session)
        items, total = list_scholarships(session, ScholarshipQuery())
        listed = {item.id for item in items}
        assert listed == {ids["live"]}
        assert total == 1
        assert ids["review"] not in listed
        assert ids["archived"] not in listed
        assert ids["no_logo"] not in listed

    def test_an_admin_review_record_is_never_made_public_to_keep_it(self, session):
        """Phase 16, stated as a prohibition rather than a count."""
        ids = seed_mixed(session)
        publicly = set(
            session.scalars(select(Scholarship.id).where(*public_visibility_conditions())).all()
        )
        under_review = set(
            session.scalars(select(Scholarship.id).where(or_(*admin_review_conditions()))).all()
        )
        assert ids["review"] not in publicly
        assert ids["review"] in under_review
        # The two sets are genuinely different populations, not two names for one.
        assert publicly != under_review

    def test_a_record_missing_its_logo_is_hidden_but_not_deletable(self, session):
        ids = seed_mixed(session)
        decision = next(d for d in scan(session, as_of=AS_OF) if d.scholarship_id == ids["no_logo"])
        assert decision.bucket != BUCKET_LIVE
        assert decision.is_keep

    def test_a_cleanup_dry_run_leaves_the_public_count_untouched(self, session):
        before = catalogue_counts(session)
        dry_run(session, as_of=AS_OF, run_id="vis-1", policy=DELETING)
        assert catalogue_counts(session) == before

    def test_a_deletion_run_leaves_the_public_count_untouched(self, session, tmp_ledger):
        """Phase 15: the public catalogue must not move."""
        ids = seed_mixed(session)
        before = catalogue_counts(session)
        # Every stored record is either live, protected, or reviewable here, so a
        # correct run removes nothing and the public total cannot shift.
        report = delete_bounded(
            session, [ids["archived"]], as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="vis-2"
        )
        after = catalogue_counts(session)
        assert report["reconciliation"]["checks"]["public_total_unchanged"] is True
        assert after["public_total"] == before["public_total"]
        assert after["row_total"] == before["row_total"]


class TestAdminVisibility:
    def test_an_admin_review_record_is_still_discoverable(self, session):
        ids = seed_mixed(session)
        from app.routers.admin_image_review import review_queue_counts

        counts = review_queue_counts(session)
        assert counts["scholarships_needing_review"] == 1
        assert counts["pending_scholarship_reviews"] == 0

    def test_a_pending_review_is_visible_to_the_admin_queue(self, session):
        ids = seed_mixed(session)
        session.add(
            ScholarshipReview(
                scholarship_id=ids["archived"], field_name="status",
                conflict_reason="unresolved", verification_state="needs_review",
                decision="pending",
            )
        )
        session.commit()
        from app.routers.admin_image_review import review_queue_counts

        assert review_queue_counts(session)["pending_scholarship_reviews"] == 1
        assert stored(session, ids["archived"]) is True

    def test_a_pending_image_review_is_visible_to_the_admin_queue(self, session):
        ids = seed_mixed(session)
        session.add(
            ImageReview(
                scholarship_id=ids["review"], image_url="https://review.test/logo.png",
                image_kind="official_logo", confidence="LOW", decision="pending",
            )
        )
        session.commit()
        from app.routers.admin_image_review import review_queue_counts

        counts = review_queue_counts(session)
        assert counts["pending_image_reviews"] == 1
        assert stored(session, ids["review"]) is True

    def test_a_retention_run_never_removes_a_reviewable_record(self, session, tmp_ledger):
        ids = seed_mixed(session)
        rows = [make_candidate(session, 200 + i) for i in range(3)]
        candidates = [d.scholarship_id for d in scan(session, as_of=AS_OF) if d.is_delete]
        session.add(
            ImageReview(
                scholarship_id=candidates[0], image_url="https://old.test/logo.png",
                image_kind="official_logo", confidence="LOW", decision="pending",
            )
        )
        session.commit()
        report = delete_bounded(session, candidates, as_of=AS_OF, policy=DELETING, ledger=tmp_ledger, run_id="adm-1")
        assert candidates[0] not in report["deleted"]
        assert stored(session, candidates[0]) is True
        assert len(report["deleted"]) == len(candidates) - 1
