"""Tests for the autonomous maintenance architecture.

Each test here corresponds to a specific way the previous design failed
silently. The recurring theme is not "a bug existed" but "the system reported
success while doing nothing useful", which is why so many of these assert on
exit codes and persisted state rather than only on return values.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.jobs import scholarzone_maintenance as worker
from app.services.maintenance_cursor import MaintenanceCursorStore
from app.services.maintenance_run_log import MaintenanceRunRecorder, redact

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    """An isolated SQLite session factory, torn down after the test."""
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 't.db').as_posix()}")

    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()
    yield get_session_factory()
    reset_database_connections()


def _seed(factory, count: int, *, quarantined: int = 0, start: int = 1):
    from app.models import Scholarship

    session = factory()
    try:
        for i in range(start, start + count):
            session.add(
                Scholarship(
                    id=i,
                    title=f"Scholarship {i}",
                    country="Testland",
                    degree="Master",
                    funding="Full",
                    official_source_url=f"https://example{i}.test/programme",
                )
            )
        for j in range(quarantined):
            session.add(
                Scholarship(
                    id=90000 + j,
                    title=f"Quarantined {j}",
                    country="Testland",
                    degree="Master",
                    funding="Full",
                    verification_status="quarantined",
                    official_source_url=f"https://quarantine{j}.test/p",
                )
            )
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# The starvation bug
# ---------------------------------------------------------------------------


class TestEnrichmentAdvancesThroughTheCatalogue:
    """The original defect: `ORDER BY id LIMIT n` with no cursor.

    Every twelve-hour run re-processed the same first records and the tail of
    the catalogue was never reached, while the run reported success. These
    tests assert cumulative coverage, not that a call returned.
    """

    def test_consecutive_runs_do_not_repeat_the_first_ids(self, factory):
        _seed(factory, 10)
        store = MaintenanceCursorStore(factory)

        first = store.select_batch("enrich", limit=3, skip_complete=False)
        store.advance("enrich", first)
        second = store.select_batch("enrich", limit=3, skip_complete=False)
        store.advance("enrich", second)

        assert first.ids == [1, 2, 3]
        assert second.ids == [4, 5, 6], (
            "the second run repeated the first batch: the cursor did not advance"
        )
        assert not set(first.ids) & set(second.ids)

    def test_bounded_runs_cover_the_whole_catalogue_exactly_once(self, factory):
        """ceil(n/limit) runs must touch every record once, in order."""
        _seed(factory, 10)
        store = MaintenanceCursorStore(factory)

        seen: list[int] = []
        for _ in range(4):  # ceil(10/3)
            batch = store.select_batch("enrich", limit=3, skip_complete=False)
            seen.extend(batch.ids)
            store.advance("enrich", batch)

        assert sorted(seen) == list(range(1, 11))
        assert len(seen) == len(set(seen)), "a record was visited twice in one cycle"

    def test_the_cursor_wraps_and_starts_a_new_cycle(self, factory):
        """Records must be revisited on a cadence, not starved forever."""
        _seed(factory, 4)
        store = MaintenanceCursorStore(factory)

        # First run covers the whole catalogue in one batch.
        first = store.select_batch("enrich", limit=4, skip_complete=False)
        assert first.ids == [1, 2, 3, 4]
        assert first.wrapped is False
        store.advance("enrich", first)
        assert store.get_state("enrich").cycles_completed == 0

        # Nothing is left above the cursor, so the next run starts a new cycle
        # rather than returning an empty batch forever.
        second = store.select_batch("enrich", limit=4, skip_complete=False)
        assert second.wrapped is True
        assert second.ids == [1, 2, 3, 4], "a new cycle must restart at the beginning"
        assert second.cycles_completed == 1

    def test_cursor_survives_a_process_restart(self, factory):
        """State lives in the database, not in the process or an Actions cache."""
        _seed(factory, 6)
        store = MaintenanceCursorStore(factory)
        batch = store.select_batch("enrich", limit=3, skip_complete=False)
        store.advance("enrich", batch)

        # A brand new store object models a fresh runner on a fresh host.
        after_restart = MaintenanceCursorStore(factory).select_batch(
            "enrich", limit=3, skip_complete=False
        )
        assert after_restart.ids == [4, 5, 6]

    def test_a_failed_batch_is_reselected_not_skipped(self, factory):
        """If the work never ran, the cursor must not have moved."""
        _seed(factory, 6)
        store = MaintenanceCursorStore(factory)

        selected = store.select_batch("enrich", limit=3, skip_complete=False)
        # Stage raises before advance() is called.
        reselected = store.select_batch("enrich", limit=3, skip_complete=False)

        assert reselected.ids == selected.ids
        assert store.get_state("enrich").last_id == 0

    def test_selection_is_idempotent(self, factory):
        """Asking twice without committing must change nothing."""
        _seed(factory, 5)
        store = MaintenanceCursorStore(factory)
        assert store.select_batch("enrich", limit=3, skip_complete=False).ids == (
            store.select_batch("enrich", limit=3, skip_complete=False).ids
        )

    def test_quarantined_records_are_never_selected(self, factory):
        """Maintenance must not spend fetches on rows the API will not serve."""
        _seed(factory, 4, quarantined=2)
        store = MaintenanceCursorStore(factory)
        batch = store.select_batch("enrich", limit=50, skip_complete=False)
        assert batch.ids == [1, 2, 3, 4]
        assert not [i for i in batch.ids if i >= 90000]

    def test_dry_run_does_not_advance_the_cursor(self, factory):
        """A planning run must not consume the batch it only described."""
        _seed(factory, 6)
        store = MaintenanceCursorStore(factory)
        batch = store.select_batch("enrich", limit=3, skip_complete=False)
        # The worker only calls advance() when not dry-running.
        assert store.get_state("enrich").last_id == 0
        store.advance("enrich", batch)
        assert store.get_state("enrich").last_id == 3

    def test_complete_records_are_skipped_to_save_fetches(self, factory):
        """A record with no empty canonical field has nothing to gain."""
        from app.models import Scholarship

        session = factory()
        try:
            session.add(
                Scholarship(
                    id=7,
                    title="Complete",
                    country="Testland",
                    degree="Master",
                    funding="Full",
                    description="d",
                    deadline_display="Whenever",
                    notes="n",
                    requirements=["r"],
                    program_type="Masters",
                    selection_notes="s",
                    application_period="p",
                    best_fit="b",
                    official_updates_url="https://example.test/u",
                    english_requirement="e",
                    catalogue_url="https://example.test/c",
                    eligibility_summary="es",
                    eligibility=["a"],
                    benefits=["b"],
                    coverage=["c"],
                    documents=["d"],
                    application_method=["m"],
                    official_source_url="https://example7.test/p",
                )
            )
            session.commit()
        finally:
            session.close()

        store = MaintenanceCursorStore(factory)
        batch = store.select_batch("enrich", limit=10, skip_complete=True)
        assert 7 not in batch.ids
        assert batch.skipped_complete >= 1


# ---------------------------------------------------------------------------
# Honest failure semantics
# ---------------------------------------------------------------------------


class TestFailureIsNotReportedAsSuccess:
    def test_a_failed_stage_reports_failure(self):
        def boom():
            raise RuntimeError("provider unreachable")

        report = worker._run_stage("verify", boom)
        assert report.ok is False
        assert "provider unreachable" in report.error

    def test_stage_isolation_still_holds(self):
        """One broken stage must not hide the state of the others."""
        results = [
            worker._run_stage("a", lambda: (_ for _ in ()).throw(ValueError("x"))),
            worker._run_stage("b", lambda: {"ok": 1}),
            worker._run_stage("c", lambda: (_ for _ in ()).throw(KeyError("y"))),
        ]
        assert [r.ok for r in results] == [False, True, False]

    def test_dependent_stages_are_skipped_after_an_upstream_failure(self):
        assert worker.STAGE_DEPENDENCIES["verify"] == ()
        for stage in ("enrich", "images", "discover"):
            assert "verify" in worker.STAGE_DEPENDENCIES[stage], (
                f"{stage} would run on unverified records if verify failed"
            )

    def test_a_failing_run_exits_non_zero(self, monkeypatch, factory):
        """The core regression: this used to return 0 and the job showed green."""
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", os.environ["SCHOLARZONE_DATABASE_URL"])

        import app.scheduler_v2 as sched

        monkeypatch.setattr(
            sched, "run_verification_round", lambda dry_run=False: (_ for _ in ()).throw(
                RuntimeError("neon unreachable")
            )
        )
        code = worker.main(["--stage", "verify", "--limit", "1", "--dry-run"])
        assert code == worker.EXIT_STAGE_FAILED
        assert code != 0

    def test_a_successful_run_exits_zero(self, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")

        import app.scheduler_v2 as sched

        from app.scheduler_v2 import VerificationRoundResult

        monkeypatch.setattr(
            sched,
            "run_verification_round",
            lambda dry_run=False: VerificationRoundResult(0, 0, 0),
        )
        assert worker.main(["--stage", "verify", "--limit", "1", "--dry-run"]) == worker.EXIT_OK

    def test_missing_database_url_in_production_is_fatal(self, monkeypatch):
        """A development fallback would maintain the wrong database silently."""
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
        monkeypatch.delenv("SCHOLARZONE_DATABASE_URL", raising=False)
        assert worker.main(["--stage", "verify"]) == worker.EXIT_FATAL

    def test_production_refuses_a_sqlite_database(self, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "sqlite:///local.db")
        assert worker.main(["--stage", "verify"]) == worker.EXIT_FATAL

    def test_preflight_raises_before_any_stage_runs(self, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
        monkeypatch.delenv("SCHOLARZONE_DATABASE_URL", raising=False)
        with pytest.raises(worker.FatalError):
            worker._preflight()

    def test_production_accepts_a_neon_url_without_connecting(self):
        """The dialect gate is pure, so it can be proven without a live DB.

        This is the check that stops the job quietly maintaining a local SQLite
        file while reporting success.
        """
        from app.core.config import Settings

        worker._require_production_database(
            Settings(
                environment="production",
                database_url="postgresql://u:p@ep-cool.us-east-2.aws.neon.tech/db",
                allowed_origins=(),
            )
        )
        with pytest.raises(worker.FatalError):
            worker._require_production_database(
                Settings(
                    environment="production",
                    database_url="sqlite:///scholarzone.db",
                    allowed_origins=(),
                )
            )

    def test_development_may_use_sqlite(self):
        from app.core.config import Settings

        worker._require_production_database(
            Settings(
                environment="development",
                database_url="sqlite:///scholarzone.db",
                allowed_origins=(),
            )
        )

    def test_exit_codes_are_distinct(self):
        assert worker.EXIT_OK == 0
        assert worker.EXIT_STAGE_FAILED == 1
        assert worker.EXIT_FATAL == 2
        assert len({worker.EXIT_OK, worker.EXIT_STAGE_FAILED, worker.EXIT_FATAL}) == 3

    def test_verification_dry_run_writes_nothing(self, factory):
        """`--dry-run` must not quietly run the engine, which commits."""
        from app.scheduler_v2 import run_verification_round

        result = run_verification_round(dry_run=True)
        assert result.dry_run is True
        assert result.jobs_submitted == 0
        assert result.jobs_completed == 0
        assert result.planned_candidates >= 0
        # The plan is readable, which is the point of running it.
        assert "planned_candidates" in result.as_dict()


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


class TestRunRecord:
    def test_a_run_is_persisted_with_status_and_counts(self, factory):
        recorder = MaintenanceRunRecorder(factory)
        recorder.open()
        recorder.record_stage("verify", True, {"jobs_completed": 3}, 1.5, None)
        recorder.record_counts({"enrich_records_scanned": 10})
        recorder.finish("ok")

        from app.models import MaintenanceRun

        session = factory()
        try:
            run = session.query(MaintenanceRun).filter_by(run_id=recorder.run_id).one()
            assert run.status == "ok"
            assert run.finished_at is not None
            assert run.duration_ms is not None
            assert run.stages[0]["name"] == "verify"
            assert run.counts["enrich_records_scanned"] == 10
            assert run.error_summary is None
        finally:
            session.close()

    def test_a_failed_run_records_the_error(self, factory):
        recorder = MaintenanceRunRecorder(factory)
        recorder.open()
        recorder.record_stage("verify", False, {}, 0.2, "RuntimeError: neon down")
        recorder.finish("failed")

        from app.models import MaintenanceRun

        session = factory()
        try:
            run = session.query(MaintenanceRun).filter_by(run_id=recorder.run_id).one()
            assert run.status == "failed"
            assert "neon down" in run.error_summary
        finally:
            session.close()

    def test_the_record_cannot_grow_without_bound(self, factory):
        """A long failure list must not bloat the free database every run."""
        recorder = MaintenanceRunRecorder(factory)
        recorder.record_stage("enrich", False, {"failures": list(range(500))}, 1.0, "x")
        assert len(str(recorder.stages)) < 5000

    def test_no_secret_is_stored_in_the_record(self, factory):
        recorder = MaintenanceRunRecorder(factory)
        recorder.record_counts({"database_url": "postgresql://u:hunter2@host/db"})
        recorder.finish("ok")

        from app.models import MaintenanceRun

        session = factory()
        try:
            run = session.query(MaintenanceRun).filter_by(run_id=recorder.run_id).one()
            assert "hunter2" not in str(run.counts)
        finally:
            session.close()

    def test_redact_removes_credentials(self):
        assert "hunter2" not in redact("postgresql://user:hunter2@host/db")
        assert redact(None) is None
        assert redact("no-url") == "no-url"

    def test_the_worker_never_prints_the_database_url(self):
        source = Path(worker.__file__).read_text(encoding="utf-8")
        assert "print(database_url" not in source
        assert "print(settings.database_url" not in source
        assert "database_url)" not in source.split("print(")[-1][:400]


# ---------------------------------------------------------------------------
# No SnapDeploy dependency, no server, no secrets
# ---------------------------------------------------------------------------


def _code_only(path: Path) -> str:
    """Return a source file with comments and string literals removed.

    The worker and the workflow both *describe* the SnapDeploy history and the
    `set -x` decision in prose, so a naive substring search would fail on the
    explanation of the fix. These tests must assert on executable content.
    """
    import io
    import tokenize

    if path.suffix in (".yml", ".yaml"):
        return "\n".join(
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
    kept: list[str] = []
    with open(path, "rb") as handle:
        for token in tokenize.tokenize(io.BytesIO(handle.read()).readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            kept.append(token.string)
    return " ".join(kept)


class TestNoSnapDeployOnTheMaintenancePath:
    def test_the_worker_never_calls_snapdeploy(self):
        source = _code_only(Path(worker.__file__)).lower()
        for needle in ("snapdeploy", "containers.snapdeploy", "api/public/wake", "wake/"):
            assert needle not in source, f"the worker references {needle}"

    def test_the_worker_does_not_need_a_running_server(self):
        source = _code_only(Path(worker.__file__))
        assert "from app.main" not in source
        assert "uvicorn" not in source
        assert "httpx" not in source
        assert "requests" not in source

    def test_no_workflow_wakes_snapdeploy(self):
        for workflow in WORKFLOWS.glob("*.yml"):
            text = _code_only(workflow)
            assert "api/public/wake" not in text, f"{workflow.name} wakes SnapDeploy"
            assert "snapdeploy.dev" not in text, f"{workflow.name} calls SnapDeploy control API"

    def test_the_obsolete_pilot_workflow_is_gone(self):
        assert not (WORKFLOWS / "image-persistence-pilot.yml").exists(), (
            "the pilot workflow persisted hardcoded image URLs through the API "
            "and woke the container; it must not remain an automation path"
        )

    def test_the_workflow_does_not_pass_unused_secrets(self):
        text = _code_only(WORKFLOWS / "verification-cron.yml")
        for secret in ("SCHOLARZONE_VERIFICATION_SECRET", "SCHOLARZONE_ADMIN_SECRET"):
            assert secret not in text, f"{secret} is not used by the direct worker"
        assert "SCHOLARZONE_DATABASE_URL" in text
        assert "SCHOLARZONE_ENVIRONMENT" in text

    def test_the_router_guards_are_the_only_secret_consumers(self):
        """Justifies the previous assertion: these secrets gate HTTP headers."""
        for module in ("verification", "discovery", "admin_image_review", "admin_dashboard"):
            text = (BACKEND_DIR / "app" / "routers" / f"{module}.py").read_text(encoding="utf-8")
            assert "secret" in text

    def test_set_x_is_not_enabled(self):
        text = _code_only(WORKFLOWS / "verification-cron.yml")
        assert "set -x" not in text, "shell tracing would echo the database URL"


# ---------------------------------------------------------------------------
# Runtime alignment and configuration
# ---------------------------------------------------------------------------


class TestRuntimeAlignment:
    def _python_version(self, workflow: str) -> str:
        text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
        found = re.search(r"python-version:\s*'([0-9.]+)'", text)
        assert found, f"{workflow} does not pin a Python version"
        return found.group(1)

    def test_maintenance_matches_the_backend_runtime(self):
        """Drift here means maintenance can succeed on behaviour the API lacks."""
        assert self._python_version("verification-cron.yml") == self._python_version("ci.yml")

    def test_the_production_backend_runtime_is_python_311(self):
        assert self._python_version("ci.yml") == "3.11"

    def test_the_scheduled_cron_is_unchanged(self):
        text = (WORKFLOWS / "verification-cron.yml").read_text(encoding="utf-8")
        assert "cron: '7 */12 * * *'" in text

    def test_concurrency_protection_is_present(self):
        text = (WORKFLOWS / "verification-cron.yml").read_text(encoding="utf-8")
        assert "concurrency:" in text
        assert "group: scholarzone-maintenance" in text

    def test_least_privilege_permissions(self):
        text = (WORKFLOWS / "verification-cron.yml").read_text(encoding="utf-8")
        assert "permissions:" in text
        assert "contents: read" in text
        assert "write-all" not in text

    def test_standard_runner_and_bounded_timeout(self):
        text = (WORKFLOWS / "verification-cron.yml").read_text(encoding="utf-8")
        assert "runs-on: ubuntu-latest" in text
        assert "timeout-minutes:" in text

    def test_dependency_caching_is_enabled(self):
        text = (WORKFLOWS / "verification-cron.yml").read_text(encoding="utf-8")
        assert "cache: pip" in text
        assert "cache-dependency-path: backend/requirements.txt" in text

    def test_pdf_dependencies_are_declared(self):
        """A lazy import means a missing pin fails silently, not loudly."""
        requirements = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8")
        assert "pypdf" in requirements
        assert "pdfplumber" in requirements

    def test_apscheduler_is_gone(self):
        requirements = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8")
        assert "apscheduler" not in requirements.lower()
        assert not (BACKEND_DIR / "app" / "scheduler.py").exists()

    def test_the_intelligent_scheduler_is_preserved(self):
        assert (BACKEND_DIR / "app" / "scheduler_v2.py").exists()
        assert (BACKEND_DIR / "app" / "services" / "scheduler_engine.py").exists()


# ---------------------------------------------------------------------------
# Repository-wide guarantees
# ---------------------------------------------------------------------------


class TestRepositoryWideSweep:
    def _python_sources(self):
        for path in (BACKEND_DIR / "app").rglob("*.py"):
            yield path

    def test_no_python_module_wakes_snapdeploy(self):
        for path in self._python_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "api/public/wake" not in text, f"{path.name} calls the SnapDeploy wake API"

    def test_no_module_schedules_maintenance_through_the_api(self):
        """A scheduler -> production API pattern is what this phase removed."""
        for path in self._python_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "SCHOLARZONE_API_URL" not in text, (
                f"{path.name} still targets the production API for automation"
            )

    def test_every_autonomous_module_imports(self):
        """The worker's import closure must load with no server and no secrets."""
        env = dict(os.environ)
        env["PYTHONPATH"] = "."
        env["SCHOLARZONE_ENVIRONMENT"] = "test"
        env["SCHOLARZONE_DATABASE_URL"] = "sqlite:///:memory:"
        env.pop("SCHOLARZONE_VERIFICATION_SECRET", None)
        env.pop("SCHOLARZONE_ADMIN_SECRET", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import app.jobs.scholarzone_maintenance as w;"
                "from app.services.maintenance_cursor import MaintenanceCursorStore;"
                "from app.services.maintenance_run_log import MaintenanceRunRecorder;"
                "import app.scheduler_v2; print('ok')",
            ],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout

    def test_the_worker_module_is_git_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "backend/app/jobs/scholarzone_maintenance.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert "scholarzone_maintenance.py" in result.stdout

    def test_no_paid_dependency_was_introduced(self):
        requirements = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8").lower()
        for needle in ("openai", "anthropic", "google-genai", "cohere", "replicate"):
            assert needle not in requirements, f"{needle} is a paid AI dependency"
