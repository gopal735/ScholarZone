"""Regression tests ensuring all production modules exist, are importable, and are git-tracked.

Regression for the incident where discovery_scheduler.py existed locally but was not
tracked in Git, causing production ModuleNotFoundError. These tests generalize to
detect ANY production module missing from the build artifact.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Critical modules organized by category.
# Derived from actual imports in app/main.py and the full app/ tree.
# ---------------------------------------------------------------------------
CRITICAL_MODULES = {
    "core": [
        "app.core.config",
    ],
    "routers": [
        "app.routers.scholarships",
        "app.routers.verification",
        "app.routers.admin_image_review",
        "app.routers.discovery",
        "app.routers.admin_dashboard",
    ],
    "services": [
        "app.services.scholarships",
        "app.services.scholarship_verifier",
        "app.services.discovery_scheduler",
        "app.services.image_discovery",
        "app.services.source_resolver",
        "app.services.scholarship_recovery",
        "app.services.scholarship_retry",
        "app.services.scholarship_review",
        "app.services.scholarship_updater",
        "app.services.scholarship_ingestion",
        "app.services.self_healing_verification",
        "app.services.verification_intelligence",
        "app.services.verification_cost_optimizer",
        "app.services.adaptive_policy",
        "app.services.confidence_decay",
        "app.services.freshness_governance",
        "app.services.knowledge_graph",
        "app.services.lifecycle_manager",
        "app.services.lifecycle_identity",
        "app.services.content_fingerprinting",
        "app.services.evidence_arbitration",
        "app.services.dependency_graph",
        "app.services.counterfactual_safety",
        "app.services.anomaly_detection",
        "app.services.entity_resolution",
        "app.services.feedback_calibration",
        "app.services.error_classification",
        "app.services.discovery_config",
        "app.services.discovery_identity",
        "app.services.discovery_pipeline",
        "app.services.scheduler_engine",
        "app.services.scheduler_queue",
        "app.services.scheduler_config",
        "app.services.scheduler_priority",
        "app.services.scholarship_diff",
        "app.services.scholarship_evidence",
        "app.services.scholarship_extractor",
        "app.services.scholarship_fetch_executor",
        "app.services.scholarship_history",
        "app.services.scholarship_image_verifier",
        "app.services.image_analysis",
        "app.services.image_validator",
        "app.services.email_service",
        "app.services.official_source_fetcher",
        "app.services.next_cycle_discovery",
        "app.services.information_gain_scheduler",
        "app.services.source_adapter",
        "app.services.source_adapter_executor",
        "app.services.source_health_service",
        "app.services.change_impact_staleness",
        "app.services.admin_image_review",
        "app.services.telemetry",
        "app.services.telemetry_decorators",
        "app.services.telemetry_tracing",
        "app.services.temporal_versioning",
        "app.services.verification_confidence",
        "app.services.temporal_versioning",
    ],
    "data": [
        "app.data.additional_scholarships",
        "app.data.verified_scholarships",
    ],
    "repositories": [
        "app.repositories.scholarships",
    ],
    "models": [
        "app.models",
    ],
    "core_modules": [
        "app.database",
        "app.main",
        "app.seed",
        "app.schemas",
    ],
}

ALL_CRITICAL_MODULES = [
    mod for modules in CRITICAL_MODULES.values() for mod in modules
]

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _module_to_path(module_name: str) -> Path:
    """Convert a dotted module name to an expected .py file path under backend/."""
    relative = module_name.replace(".", "/") + ".py"
    return BACKEND_DIR / relative


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def git_tracked_files() -> set[str] | None:
    """Return set of git-tracked .py files under backend/app/, or None if git unavailable."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip().startswith("app/") and line.strip().endswith(".py")
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCriticalModulesExistOnDisk:
    """Every critical module must have a .py file on disk."""

    @pytest.mark.parametrize("module_name", ALL_CRITICAL_MODULES)
    def test_module_file_exists(self, module_name: str):
        expected = _module_to_path(module_name)
        assert expected.exists(), f"{module_name} expected at {expected} but file missing"


class TestCriticalModulesImportable:
    """Every critical module must be importable in the local source tree."""

    @pytest.mark.parametrize("module_name", list(CRITICAL_MODULES["routers"]))
    def test_router_importable(self, module_name: str):
        importlib.import_module(module_name)

    @pytest.mark.parametrize("module_name", list(CRITICAL_MODULES["services"]))
    def test_service_importable(self, module_name: str):
        importlib.import_module(module_name)

    @pytest.mark.parametrize("module_name", list(CRITICAL_MODULES["models"]))
    def test_model_importable(self, module_name: str):
        importlib.import_module(module_name)

    @pytest.mark.parametrize("module_name", list(CRITICAL_MODULES["core"]))
    def test_core_importable(self, module_name: str):
        importlib.import_module(module_name)

    @pytest.mark.parametrize("module_name", list(CRITICAL_MODULES["data"]))
    def test_data_importable(self, module_name: str):
        importlib.import_module(module_name)

    @pytest.mark.parametrize("module_name", list(CRITICAL_MODULES["repositories"]))
    def test_repository_importable(self, module_name: str):
        importlib.import_module(module_name)

    @pytest.mark.parametrize("module_name", list(CRITICAL_MODULES["core_modules"]))
    def test_core_module_importable(self, module_name: str):
        importlib.import_module(module_name)


def test_main_app_imports_successfully():
    """app.main must be importable without error — the FastAPI app must assemble."""
    importlib.import_module("app.main")


class TestNoCriticalModuleMissingFromGit:
    """Regression: a file exists locally but is not tracked in Git (the original incident)."""

    def test_all_critical_modules_tracked(self, git_tracked_files):
        if git_tracked_files is None:
            pytest.skip("git is not available in this environment")

        missing = []
        for module_name in ALL_CRITICAL_MODULES:
            expected_path = module_name.replace(".", "/") + ".py"
            if expected_path not in git_tracked_files:
                missing.append(expected_path)

        assert not missing, (
            "The following critical modules are NOT tracked in git. "
            "They exist locally but were not committed:\n"
            + "\n".join(f"  - {p}" for p in missing)
        )
