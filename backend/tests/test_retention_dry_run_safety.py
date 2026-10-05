"""Phase 6 - the dry run, proven non-destructive by reading its SQL.

The claim being tested is narrow and absolute: a dry run changes no scholarship
row. Every earlier proof of that was an assertion about the *code* - this one is
an assertion about the *statements the database actually received*, captured with
SQLAlchemy's ``before_cursor_execute`` hook.

That distinction matters. A dry run could pass every behavioural test and still
execute an ``UPDATE`` on a table nobody thought to check, and the failure would
surface as an unexplained row diff weeks later. Capturing the SQL makes the
property checkable rather than inferred, and it is the same technique a reviewer
would use to audit it independently.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, DiscoveryCandidate, ImageReview, Scholarship, ScholarshipReview
from app.repositories.scholarships import public_visibility_conditions
from app.services.counting.catalogue import catalogue_counts
from app.services.retention_contract import RetentionPolicy, default_policy
from app.services.retention_engine import CleanupAborted, delete_bounded, dry_run

AS_OF = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
ANCIENT = datetime(2019, 1, 1, tzinfo=timezone.utc)
DELETING = RetentionPolicy(
    cleanup_enabled=True, dry_run=False, batch_size=8, max_delete_percentage=1.0
)


@pytest.fixture(autouse=True)
def production_visibility_gate(monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")
    monkeypatch.setenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE", "false")


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'dryrun.db'}")
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def statements(engine):
    """Capture every statement the database is asked to execute."""
    captured: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):
        captured.append(" ".join(statement.split()))

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield captured
    finally:
        event.remove(engine, "before_cursor_execute", record)


def _verb(sql: str) -> str:
    match = re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|BEGIN|COMMIT|ROLLBACK|PRAGMA|CREATE|DROP|ALTER)",
                     sql, re.IGNORECASE)
    return match.group(1).upper() if match else "OTHER"


def _target(sql: str) -> str:
    match = re.match(r"^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([\w\"]+)", sql, re.IGNORECASE)
    return match.group(1).strip('"').lower() if match else ""


def seed(session, tag: str = "") -> dict[str, int]:
    """One record per classification outcome, with child evidence attached.

    ``tag`` keeps the seeded official_source_urls unique so the fixture can be
    called more than once against one database, which the bounded-statement-count
    test relies on.
    """
    def u(n: str) -> str:
        return f"https://{n}.test/{tag or 'base'}"

    live = Scholarship(
        title="Listed", country="CA", degree="Master", funding="Full",
        official_source="U", official_source_url=u("live"), status="open",
        is_archived=False, is_verified=True, verification_status="active",
        image_url="https://a.test/live-logo.png", image_verified_at=ANCIENT, image_source_type="official",
    )
    no_logo = Scholarship(
        title="NoLogo", country="CA", degree="Master", funding="Full",
        official_source="U", official_source_url=u("no_logo"), status="open",
        is_archived=False, is_verified=True, verification_status="active",
    )
    review = Scholarship(
        title="Review", country="JP", degree="PhD", funding="Full",
        official_source="R", official_source_url=u("review"), status="closed",
        is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
        is_verified=False, verification_status="needs_review",
    )
    unknown = Scholarship(
        title="Unknown", country="BR", degree="Master", funding="Part",
        official_source="U", official_source_url=u("unknown"), status="closed",
        is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
        auto_delete_candidate_since=ANCIENT, is_verified=False,
        verification_status="a_state_nobody_classified",
    )
    candidate = Scholarship(
        title="Candidate", country="PE", degree="Master", funding="Part",
        official_source="O", official_source_url=u("candidate"), status="closed",
        is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
        auto_delete_candidate_since=ANCIENT, is_verified=False, verification_status="inactive",
        deadline_date=date(2018, 6, 1),
    )
    with_evidence = Scholarship(
        title="HasEvidence", country="ZA", degree="Master", funding="Part",
        official_source="E", official_source_url=u("with_evidence"), status="closed",
        is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
        auto_delete_candidate_since=ANCIENT, is_verified=False, verification_status="inactive",
        deadline_date=date(2018, 6, 1),
    )
    grace = Scholarship(
        title="GraceOnly", country="NG", degree="Master", funding="Part",
        official_source="G", official_source_url=u("grace"), status="closed",
        is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
        auto_delete_candidate_since=AS_OF - timedelta(days=3), is_verified=False,
        verification_status="inactive", deadline_date=date(2018, 6, 1),
    )
    session.add_all([live, no_logo, review, unknown, candidate, with_evidence, grace])
    session.commit()

    session.add(
        ScholarshipReview(
            scholarship_id=with_evidence.id, field_name="status",
            conflict_reason="settled", verification_state="confirmed",
            decision="confirmed", reviewed_at=ANCIENT, reviewed_by="operator",
        )
    )
    session.add(
        ScholarshipReview(
            scholarship_id=review.id, field_name="status", conflict_reason="open",
            verification_state="needs_review", decision="pending",
        )
    )
    session.add(
        ImageReview(
            scholarship_id=review.id, image_url="https://a.test/review-logo.png",
            image_kind="official_logo", confidence="LOW", decision="pending",
        )
    )
    session.add(
        DiscoveryCandidate(
            source_url=u("candidate"), normalized_url=u("candidate"),
            discovery_hash=f"h-{tag or 'base'}", status="resolved", match_status="rejected",
            matched_scholarship_id=candidate.id, resolved_at=ANCIENT,
        )
    )
    session.commit()
    return {
        "live": live.id, "no_logo": no_logo.id, "review": review.id,
        "unknown": unknown.id, "candidate": candidate.id,
        "with_evidence": with_evidence.id, "grace": grace.id,
    }


class TestDryRunIssuesNoDestructiveStatement:
    def test_no_delete_statement_is_ever_issued(self, session, statements):
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-1", policy=DELETING)
        deletes = [s for s in statements if _verb(s) == "DELETE"]
        assert deletes == [], f"a dry run issued DELETE: {deletes}"

    def test_no_update_outside_the_run_ledger_is_ever_issued(self, session, statements):
        """No UPDATE anywhere except the engine's own run row.

        The run ledger legitimately sees an INSERT when the run opens and an
        UPDATE when it closes, because the row is written up front so a crash
        still leaves a trace. What must never happen is an UPDATE to a catalogue
        or evidence table, so the assertion is scoped to that rather than
        forbidding the word.
        """
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-2", policy=DELETING)
        offending = [
            s for s in statements
            if _verb(s) == "UPDATE" and _target(s) != "maintenance_runs"
        ]
        assert offending == [], f"a dry run issued UPDATE outside the ledger: {offending}"

    def test_no_scholarship_table_is_written_at_all(self, session, statements):
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-3", policy=DELETING)
        written = [
            s for s in statements
            if _verb(s) in {"INSERT", "UPDATE", "DELETE"} and _target(s) == "scholarships"
        ]
        assert written == [], f"a dry run wrote to scholarships: {written}"

    def test_no_child_evidence_table_is_touched(self, session, statements):
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-4", policy=DELETING)
        evidence_tables = {
            "scholarship_reviews", "scholarship_verification_history",
            "scholarship_snapshots", "scholarship_restore_records",
            "image_reviews", "scholarship_fetch_attempts", "discovery_candidates",
        }
        touched = [
            s for s in statements
            if _verb(s) in {"INSERT", "UPDATE", "DELETE"} and _target(s) in evidence_tables
        ]
        assert touched == [], f"a dry run wrote to a child evidence table: {touched}"

    def test_the_only_writes_are_to_the_run_ledger(self, session, statements):
        """One INSERT to open the run, one UPDATE to close it, nothing else."""
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-5", policy=DELETING)
        writes = [s for s in statements if _verb(s) in {"INSERT", "UPDATE", "DELETE"}]
        targets = {_target(s) for s in writes}
        assert targets == {"maintenance_runs"}, f"writes went to {sorted(targets)}"
        verbs = [_verb(s) for s in writes]
        assert verbs == ["INSERT", "UPDATE"], writes

    def test_no_schema_statement_is_issued(self, session, statements):
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-6", policy=DELETING)
        ddl = [s for s in statements if _verb(s) in {"CREATE", "DROP", "ALTER"}]
        assert ddl == []

    def test_the_canonical_visibility_predicate_is_the_only_source(self, session, statements):
        """No ad-hoc visibility SQL: the catalogue's own predicate is what runs.

        Asserted on the rendered shape rather than on the SQLAlchemy expression
        tree, because this is the statement the database received. The bound
        parameter is rendered as ``?``, so the check looks for the predicate's
        structure - the verification-status exclusion and the archive exclusion -
        which is what a second, divergent copy of the rule would lack.
        """
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-7", policy=DELETING)
        visibility = [
            s for s in statements
            if _verb(s) == "SELECT"
            and "FROM scholarships" in s
            and "scholarships.verification_status" in s
            and "is_archived" in s
        ]
        assert visibility, "the scan should resolve LIVE through the canonical predicate"
        assert any(
            "scholarships.verification_status != ?" in s for s in visibility
        ), visibility
        assert any(
            re.search(r"scholarships\.is_archived IS (1|true|false|NOT )?", s, re.I)
            for s in visibility
        ), visibility

    def test_query_scope_is_the_scholarship_table(self, session, statements):
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-8", policy=DELETING)
        tables_read = set()
        for sql in statements:
            if _verb(sql) != "SELECT":
                continue
            for match in re.finditer(r"\bFROM\s+([\w\"]+)", sql, re.IGNORECASE):
                tables_read.add(match.group(1).strip('"').lower())
            for match in re.finditer(r"\bJOIN\s+([\w\"]+)", sql, re.IGNORECASE):
                tables_read.add(match.group(1).strip('"').lower())
        # Nothing outside the catalogue and its evidence may be read.
        assert tables_read <= {
            "scholarships", "scholarship_reviews", "scholarship_verification_history",
            "scholarship_snapshots", "scholarship_restore_records", "image_reviews",
            "scholarship_fetch_attempts", "discovery_candidates", "maintenance_runs",
            "saved_scholarships", "application_records",
            "scholarship_supervisor_coverage", "scholarship_professor_links",
            "supervisor_source_evidence", "professor_outreach_records",
        }, sorted(tables_read)

    def test_bounded_statement_count(self, session, statements):
        """A dry run over a fixed catalogue issues a fixed number of statements.

        Not a performance claim. It is a scope claim: the count cannot grow with
        the number of records, because the scan is one pass with conditional
        aggregates rather than a query per row.
        """
        seed(session)
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-9", policy=DELETING)
        small = len(statements)
        for index in range(20):
            seed(session, tag=f"x{index}")
        statements.clear()
        dry_run(session, as_of=AS_OF, run_id="sql-10", policy=DELETING)
        large = len(statements)
        assert large == small, (
            f"statement count grew with the dataset ({small} -> {large}); the scan should "
            "be one pass, not a query per row"
        )


class TestDryRunMutatesNothingObservable:
    def test_no_scholarship_row_changes(self, session):
        seed(session)
        session.expire_all()
        before = {
            row.id: (row.title, row.status, row.verification_status, row.is_archived,
                     row.is_verified, row.deletion_protected, row.archived_at,
                     row.auto_delete_candidate_since)
            for row in session.scalars(select(Scholarship)).all()
        }
        dry_run(session, as_of=AS_OF, run_id="obs-1", policy=DELETING)
        session.expire_all()
        after = {
            row.id: (row.title, row.status, row.verification_status, row.is_archived,
                     row.is_verified, row.deletion_protected, row.archived_at,
                     row.auto_delete_candidate_since)
            for row in session.scalars(select(Scholarship)).all()
        }
        assert after == before

    def test_no_child_evidence_row_changes(self, session):
        ids = seed(session)
        session.expire_all()
        reviews = session.query(ScholarshipReview).count()
        images = session.query(ImageReview).count()
        candidates = session.query(DiscoveryCandidate).count()
        linked = [
            c.matched_scholarship_id
            for c in session.scalars(select(DiscoveryCandidate)).all()
        ]
        dry_run(session, as_of=AS_OF, run_id="obs-2", policy=DELETING)
        session.expire_all()
        assert session.query(ScholarshipReview).count() == reviews
        assert session.query(ImageReview).count() == images
        assert session.query(DiscoveryCandidate).count() == candidates
        assert [
            c.matched_scholarship_id for c in session.scalars(select(DiscoveryCandidate)).all()
        ] == linked
        assert ids["candidate"] in linked

    def test_public_counts_are_identical_before_and_after(self, session):
        seed(session)
        before = catalogue_counts(session)
        dry_run(session, as_of=AS_OF, run_id="obs-3", policy=DELETING)
        assert catalogue_counts(session) == before

    def test_the_only_new_row_is_the_audit_entry(self, session):
        from app.models import MaintenanceRun

        seed(session)
        dry_run(session, as_of=AS_OF, run_id="obs-4", policy=DELETING)
        runs = session.query(MaintenanceRun).all()
        assert [r.run_id for r in runs] == ["obs-4"]
        assert runs[0].dry_run is True


class TestDryRunDeterminism:
    def test_repeated_runs_agree_on_every_field(self, session):
        seed(session)
        first = dry_run(session, as_of=AS_OF, run_id="det-1", trigger="t", policy=DELETING)
        second = dry_run(session, as_of=AS_OF, run_id="det-2", trigger="t", policy=DELETING)
        for key in ("summary", "guards", "guard_failures", "delete_candidates",
                    "counts_before", "policy", "reference_integrity", "recovery"):
            assert first[key] == second[key], f"{key} differed between identical runs"

    def test_only_the_run_identity_and_timing_differ(self, session):
        """Everything the report *decides* is identical between identical runs.

        ``elapsed_seconds`` is excluded deliberately. It is a measurement of the
        machine, not a property of the catalogue, and asserting it matched would
        be asserting that the run took the same time twice - which is false, and
        would fail intermittently on a loaded CI box for no useful reason.
        """
        seed(session)
        first = dry_run(session, as_of=AS_OF, run_id="det-3", policy=DELETING)
        second = dry_run(session, as_of=AS_OF, run_id="det-4", policy=DELETING)
        assert first["run_id"] != second["run_id"]
        volatile = {"run_id", "elapsed_seconds"}
        stripped_a = {k: v for k, v in first.items() if k not in volatile}
        stripped_b = {k: v for k, v in second.items() if k not in volatile}
        assert stripped_a == stripped_b

    def test_the_timing_field_is_measured_not_declared(self, session):
        seed(session)
        report = dry_run(session, as_of=AS_OF, run_id="det-5", policy=DELETING)
        assert isinstance(report["elapsed_seconds"], float)
        assert report["elapsed_seconds"] >= 0.0

    def test_manifest_generation_is_deterministic(self, tmp_path):
        """The same entries produce byte-identical output."""
        from app.services.retention_engine import append_deletion_manifest

        entry = {
            "run_id": "det", "run_token": "det-1", "mode": "DELETE",
            "deleted_at": "2026-10-05T12:00:00+00:00", "deleted": 1, "ids": [1],
            "records": [{"scholarship_id": 1}], "confirmed": True,
            "contract_version": "live-admin-review-retention/2",
        }
        first = tmp_path / "a.json"
        second = tmp_path / "b.json"
        append_deletion_manifest(entry, path=first)
        append_deletion_manifest(entry, path=second)
        assert first.read_bytes() == second.read_bytes()

    def test_an_unconfirmed_entry_is_replaced_by_its_confirmation(self, tmp_path):
        """The write-before-commit discipline must not double-count a record."""
        from app.services.retention_engine import append_deletion_manifest

        path = tmp_path / "ledger.json"
        base = {
            "run_id": "r1", "run_token": "r1-1", "mode": "DELETE",
            "deleted_at": "2026-10-05T12:00:00+00:00", "deleted": 0, "ids": [],
            "records": [], "confirmed": False,
        }
        append_deletion_manifest(base, path=path)
        append_deletion_manifest({**base, "deleted": 1, "ids": [7], "confirmed": True}, path=path)
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["retention_summary"]["retention_deleted"] == 1
        assert len(written["retention_batches"]) == 1
        assert written["retention_batches"][0]["confirmed"] is True


class TestUncertainRecordsStayKept:
    def test_the_unknown_record_is_not_a_candidate(self, session):
        ids = seed(session)
        report = dry_run(session, as_of=AS_OF, run_id="keep-1", policy=DELETING)
        candidates = {c["scholarship_id"] for c in report["delete_candidates"]}
        assert ids["unknown"] not in candidates
        assert report["summary"]["states"]["UNKNOWN"] >= 1

    def test_the_grace_record_is_eligible_but_not_a_candidate(self, session):
        ids = seed(session)
        report = dry_run(session, as_of=AS_OF, run_id="keep-2", policy=DELETING)
        states = report["summary"]["states"]
        candidates = {c["scholarship_id"] for c in report["delete_candidates"]}
        assert states.get("GRACE_ELIGIBLE", 0) >= 1
        assert report["summary"]["grace_eligible"] >= 1
        assert ids["grace"] not in candidates

    def test_the_evidence_record_is_not_a_candidate(self, session):
        ids = seed(session)
        report = dry_run(session, as_of=AS_OF, run_id="keep-3", policy=DELETING)
        candidates = {c["scholarship_id"] for c in report["delete_candidates"]}
        assert ids["with_evidence"] not in candidates

    def test_only_the_fully_qualified_record_is_a_candidate(self, session):
        ids = seed(session)
        report = dry_run(session, as_of=AS_OF, run_id="keep-4", policy=DELETING)
        assert [c["scholarship_id"] for c in report["delete_candidates"]] == [ids["candidate"]]


class TestGraceClockIsDeterministic:
    @pytest.mark.parametrize(
        "days_armed, expected_state",
        [(0, "GRACE_ELIGIBLE"), (13, "GRACE_ELIGIBLE"), (14, "DELETE_CANDIDATE"), (400, "DELETE_CANDIDATE")],
    )
    def test_the_clock_resolves_on_a_fixed_boundary(self, session, tmp_path, days_armed, expected_state):
        row = Scholarship(
            title="Clocked", country="PE", degree="Master", funding="Part",
            official_source="O", official_source_url=f"https://o.test/{days_armed}",
            status="closed", is_archived=True, archived_at=ANCIENT,
            archived_reason="deadline passed", is_verified=False,
            verification_status="inactive", deadline_date=date(2018, 6, 1),
            auto_delete_candidate_since=AS_OF - timedelta(days=days_armed),
        )
        session.add(row)
        session.commit()
        from app.services.retention_engine import scan

        decision = scan(session, as_of=AS_OF)[0]
        assert decision.state == expected_state

    def test_clearing_the_clock_reverses_eligibility(self, session):
        row = Scholarship(
            title="Reopened", country="PE", degree="Master", funding="Part",
            official_source="O", official_source_url="https://o.test/rev", status="closed",
            is_archived=True, archived_at=ANCIENT, archived_reason="deadline passed",
            is_verified=False, verification_status="inactive",
            auto_delete_candidate_since=ANCIENT,
        )
        session.add(row)
        session.commit()
        from app.services.retention_engine import scan

        assert scan(session, as_of=AS_OF)[0].state == "DELETE_CANDIDATE"
        # A reopen clears the clock, which is the whole point of persisting it.
        row.auto_delete_candidate_since = None
        session.commit()
        cleared = scan(session, as_of=AS_OF)[0]
        assert cleared.state == "GRACE_ELIGIBLE"
        assert cleared.grace_eligible is True
        assert cleared.is_keep


class TestNoProductionDatabaseRequired:
    def test_the_whole_proof_runs_offline(self, session):
        """Unit and integration proof must not need a production connection.

        Everything in this module runs against a temporary SQLite file created in
        the test's own directory. If any assertion here started requiring
        SCHOLARZONE_DATABASE_URL, the suite would be one missing secret away from
        being silently skipped - which is how a safety suite stops being run.
        """
        ids = seed(session)
        report = dry_run(session, as_of=AS_OF, run_id="offline-1", policy=DELETING)
        assert report["summary"]["scanned"] == len(ids)
        assert report["summary"]["reconciles"] is True

    def test_the_deleting_path_is_still_reachable_for_the_failure_tests(self, session):
        """The deleting path must work, or the rollback proofs would be vacuous."""
        ids = seed(session)
        report = delete_bounded(
            session, [ids["candidate"]], as_of=AS_OF, policy=DELETING,
            write_manifest=False, run_id="offline-2",
        )
        assert report["deleted"] == [ids["candidate"]]
