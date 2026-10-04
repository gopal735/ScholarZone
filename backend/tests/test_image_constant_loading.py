"""Regression tests for the two image-vocabulary NameErrors in the worker.

``87ad84c`` ("purge must not clear an image the pipeline accepted") rewrote the
import line inside ``do_stats`` from ``LOGO_IDENTITY_KINDS`` to
``ACCEPTED_IMAGE_KINDS`` instead of adding the new name to ``do_purge``, which
genuinely uses it. Both constants remained defined in the orchestrator the whole
time; the imports were simply crossed. Production then raised

    stats -> NameError: name 'LOGO_IDENTITY_KINDS' is not defined
    purge -> NameError: name 'ACCEPTED_IMAGE_KINDS' is not defined

on every scheduled run.

The existing safety tests in ``test_purge_image_safety.py`` did not catch this
because they re-implement ``do_purge``'s selection in a local ``_offenders()``
helper: they prove the *rule* is right, never that the shipped function can run.
The tests below therefore execute the real stages, and pin the scope rule that
would have caught the crossed import at commit time.

The safety property ``87ad84c`` introduced is preserved throughout and is not
weakened: an accepted image is kept whatever its kind.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone

import pytest

from app.jobs import scholarzone_maintenance as worker
from app.services import image_discovery_orchestrator as orchestrator

VOCABULARY = ("LOGO_IDENTITY_KINDS", "ACCEPTED_IMAGE_KINDS")
ORCHESTRATOR_MODULE = "app.services.image_discovery_orchestrator"
VERIFIED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)

_seq = iter(range(1, 100_000))


# ---------------------------------------------------------------------------
# The canonical vocabulary must exist and must be the orchestrator's
# ---------------------------------------------------------------------------


class TestTheCanonicalVocabularyIsDefined:
    def test_logo_identity_kinds_is_defined(self):
        assert isinstance(orchestrator.LOGO_IDENTITY_KINDS, frozenset)
        assert orchestrator.LOGO_IDENTITY_KINDS, "the identity vocabulary is empty"

    def test_accepted_image_kinds_is_defined(self):
        assert isinstance(orchestrator.ACCEPTED_IMAGE_KINDS, frozenset)
        assert orchestrator.ACCEPTED_IMAGE_KINDS, "the accepted vocabulary is empty"

    def test_the_two_vocabularies_load_from_the_worker_module(self):
        """Both names must be reachable from the worker's import graph."""
        from app.services.image_discovery_orchestrator import (  # noqa: F401
            ACCEPTED_IMAGE_KINDS,
            LOGO_IDENTITY_KINDS,
        )

    def test_accepted_includes_the_programme_photograph_and_the_banner(self):
        assert "program_image" in orchestrator.ACCEPTED_IMAGE_KINDS
        assert "official_banner" in orchestrator.ACCEPTED_IMAGE_KINDS

    def test_identity_marks_remain_a_subset_of_accepted(self):
        assert orchestrator.LOGO_IDENTITY_KINDS <= orchestrator.ACCEPTED_IMAGE_KINDS


# ---------------------------------------------------------------------------
# The defect itself: a function-local import that was written into the wrong
# function. Proven statically so it cannot recur silently.
# ---------------------------------------------------------------------------


def _module_bound_names() -> set[str]:
    tree = ast.parse(inspect.getsource(worker))
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
    return bound


def _own_scope_nodes(func: ast.FunctionDef):
    """Yield nodes belonging to ``func`` itself, pruning nested scopes.

    The stage runners are closures inside ``main``, so walking naively would
    report ``main`` as reading every name its stages read. Only a name read in
    its own scope is a candidate NameError.
    """
    stack = list(func.body)
    while stack:
        node = stack.pop()
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        ):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _scope_report() -> dict[str, dict[str, set[str]]]:
    """Per function: which vocabulary names it imports and which it reads."""
    tree = ast.parse(inspect.getsource(worker))
    module_bound = _module_bound_names()
    report: dict[str, dict[str, set[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        imported: set[str] = set()
        loaded: set[str] = set()
        for sub in _own_scope_nodes(node):
            if isinstance(sub, ast.ImportFrom) and sub.module == ORCHESTRATOR_MODULE:
                imported.update(a.asname or a.name for a in sub.names)
            elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                loaded.add(sub.id)
        report[node.name] = {
            "imported": imported,
            "loaded": loaded & set(VOCABULARY),
            "resolvable_at_module_level": module_bound,
        }
    return report


class TestEveryStageThatReadsTheVocabularyImportsIt:
    @pytest.mark.parametrize("name", VOCABULARY)
    def test_no_stage_reads_a_vocabulary_name_it_never_binds(self, name):
        offenders = []
        for func, scope in _scope_report().items():
            if name not in scope["loaded"]:
                continue
            bound_here = name in scope["imported"]
            bound_globally = name in scope["resolvable_at_module_level"]
            if not (bound_here or bound_globally):
                offenders.append(func)
        assert offenders == [], (
            f"{offenders} read {name} without importing it from "
            f"{ORCHESTRATOR_MODULE} and without a module-level binding; "
            "every reference raises NameError at runtime"
        )

    def test_stats_binds_the_vocabulary_it_reads(self):
        scope = _scope_report()["do_stats"]
        assert scope["loaded"] <= scope["imported"], (
            f"do_stats reads {sorted(scope['loaded'] - scope['imported'])} "
            "without importing them"
        )
        assert "LOGO_IDENTITY_KINDS" in scope["imported"]

    def test_purge_binds_the_vocabulary_it_reads(self):
        scope = _scope_report()["do_purge"]
        assert scope["loaded"] <= scope["imported"], (
            f"do_purge reads {sorted(scope['loaded'] - scope['imported'])} "
            "without importing them"
        )
        assert "ACCEPTED_IMAGE_KINDS" in scope["imported"]
        assert "LOGO_IDENTITY_KINDS" in scope["imported"]

    def test_no_stats_unrelated_vocabulary_binding_was_left_behind(self):
        """do_stats never reads the accepted vocabulary; it must not claim it."""
        assert "ACCEPTED_IMAGE_KINDS" not in _scope_report()["do_stats"]["imported"]

    def test_only_the_image_stages_reference_the_vocabulary(self):
        touching = {
            func for func, scope in _scope_report().items() if scope["loaded"]
        }
        assert touching == {"do_stats", "do_purge", "do_logos"}, (
            "the vocabulary reached a stage that has no image responsibility: "
            f"{sorted(touching - {'do_stats', 'do_purge', 'do_logos'})}"
        )


# ---------------------------------------------------------------------------
# The shipped stages must actually run. test_purge_image_safety.py proved the
# rule against a local re-implementation; these prove the deployed function.
# ---------------------------------------------------------------------------


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    )
    from app.database import (
        get_session_factory,
        init_database,
        reset_database_connections,
    )

    reset_database_connections()
    init_database()
    yield get_session_factory()
    reset_database_connections()


def _seed(factory, *, kind, verified_at, image_url="https://example.org/i.png"):
    from app.models import Scholarship

    session = factory()
    row = Scholarship(
        title="T",
        country="GB",
        degree="masters",
        funding="full",
        official_source_url=f"https://example.org/case-{next(_seq)}",
        is_archived=False,
        verification_status="active",
        is_verified=True,
        image_url=image_url,
        image_kind=kind,
        image_verified_at=verified_at,
    )
    session.add(row)
    session.commit()
    rid = row.id
    session.close()
    return rid


def _image_fields(session, rid) -> dict:
    from app.models import Scholarship

    row = session.get(Scholarship, rid)
    return {
        f: getattr(row, f)
        for f in (
            "image_url",
            "image_source_url",
            "image_source_type",
            "image_kind",
            "image_alt_text",
            "image_verified_at",
            "image_evaluation_status",
            "image_evaluated_at",
        )
    }


class TestTheStagesExecute:
    def test_stats_stage_raises_no_nameerror(self, factory):
        assert worker.main(["--stage", "stats"]) == worker.EXIT_OK

    def test_purge_stage_raises_no_nameerror(self, factory):
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK

    def test_stats_stage_reports_the_totals_it_measured(self, factory, capsys):
        _seed(factory, kind="program_image", verified_at=VERIFIED_AT)
        assert worker.main(["--stage", "stats"]) == worker.EXIT_OK
        assert "total" in capsys.readouterr().out.lower()


class TestPurgeKeepsAcceptedImagesAndClearsTheRest:
    def test_accepted_program_image_survives_the_real_stage(self, factory):
        rid = _seed(factory, kind="program_image", verified_at=VERIFIED_AT)
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid)["image_url"] is not None
        session.close()

    def test_accepted_official_banner_survives_the_real_stage(self, factory):
        rid = _seed(factory, kind="official_banner", verified_at=VERIFIED_AT)
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid)["image_url"] is not None
        session.close()

    def test_the_id14_shape_survives_the_real_stage(self, factory):
        """The exact shape 87ad84c existed to protect: an accepted programme photo."""
        rid = _seed(factory, kind="program_image", verified_at=VERIFIED_AT)
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid)["image_url"] is not None
        session.close()

    @pytest.mark.parametrize("kind", sorted(orchestrator.ACCEPTED_IMAGE_KINDS))
    def test_no_accepted_kind_is_cleared_because_it_is_not_a_logo(
        self, factory, kind
    ):
        rid = _seed(factory, kind=kind, verified_at=VERIFIED_AT)
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid)["image_url"] is not None
        session.close()

    def test_an_accepted_non_logo_row_keeps_every_image_field(self, factory):
        """No image field may change merely because the kind is not a logo."""
        rid = _seed(factory, kind="program_image", verified_at=VERIFIED_AT)
        session = factory()
        before = _image_fields(session, rid)
        session.close()
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid) == before
        session.close()

    def test_unaccepted_artwork_is_still_cleared(self, factory):
        rid = _seed(factory, kind="program_image", verified_at=None)
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid)["image_url"] is None
        session.close()

    def test_a_record_with_no_kind_is_still_cleared(self, factory):
        rid = _seed(factory, kind=None, verified_at=None)
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid)["image_url"] is None
        session.close()

    @pytest.mark.parametrize("kind", sorted(orchestrator.LOGO_IDENTITY_KINDS))
    def test_identity_marks_are_still_kept(self, factory, kind):
        rid = _seed(factory, kind=kind, verified_at=None)
        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK
        session = factory()
        assert _image_fields(session, rid)["image_url"] is not None
        session.close()


# ---------------------------------------------------------------------------
# Everything else must be exactly as it was
# ---------------------------------------------------------------------------


def _stage_source(name: str) -> str:
    text = inspect.getsource(worker)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{name} not found in the worker source")


class TestNothingElseMoved:
    def test_the_arming_stage_does_not_reference_image_vocabulary(self):
        source = _stage_source("do_auto_delete_candidate")
        for name in VOCABULARY:
            assert name not in source

    def test_the_deletion_stage_does_not_reference_image_vocabulary(self):
        source = _stage_source("do_purge_closed")
        for name in VOCABULARY:
            assert name not in source

    def test_the_retention_and_grace_policy_is_untouched(self):
        from app.services import auto_delete_policy

        assert auto_delete_policy.AUTO_DELETE_AFTER_DAYS == 180
        assert auto_delete_policy.DELETE_GRACE_DAYS == 14

    def test_phase_three_activation_is_untouched(self):
        assert worker.PURGE_CLOSED_EXCLUDED_FROM_ALL is False
        assert worker.DELETING_STAGE == "purge_closed"
        assert worker.ARMING_STAGE == "auto_delete_candidate"
        assert worker.STAGE_ORDER.index("auto_delete_candidate") < worker.STAGE_ORDER.index(
            "purge_closed"
        )

    def test_the_stage_inventory_is_unchanged(self):
        assert len(worker.STAGE_ORDER) == 22
        assert worker.STAGE_DEPENDENCIES["purge_closed"] == ("auto_delete_candidate",)

    def test_the_error_reporting_the_run_relies_on_is_intact(self):
        assert worker.EXIT_STAGE_FAILED != 0