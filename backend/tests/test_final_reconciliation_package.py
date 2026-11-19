"""CI coverage for the final reconciliation review package.

The package is deliberately blocked, but its internal consistency is still a
hard requirement. These tests run the same validator a reviewer would run and
prove that every forbidden mutation is caught.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PACKAGE = (
    Path(__file__).resolve().parents[1]
    / "imports"
    / "final-reconciliation-2026-11-09"
)
VALIDATOR_PATH = PACKAGE / "validate_semantics.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "final_reconciliation_validate_semantics", VALIDATOR_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_passes_semantic_validation():
    validator = _load_validator()
    report = validator.validate_package(PACKAGE)

    assert report["semantic_validation"] == "PASS", report["errors"]
    assert report["error_count"] == 0, report["errors"]
    assert report["package_status"] == "BLOCKED"
    assert report["review_package_only"] is True
    assert report["production_import_authorized"] is False
    assert report["environment"]["postgresql_simulation"] == "UNAVAILABLE"
    assert report["environment"]["duplicate_plans_executed"] == 0


def test_semantic_self_test_catches_every_mutation():
    validator = _load_validator()
    results = validator.run_self_test(PACKAGE)

    assert len(results) == 10
    missed = [item for item in results if not item["caught"]]
    assert not missed, missed


def test_canonical_insert_file_is_empty_and_legacy_archive_is_not_importable():
    inserts = json.loads(
        (PACKAGE / "final_import_ready_scholarships.json").read_text(encoding="utf-8")
    )
    assert inserts == []

    legacy = json.loads(
        (PACKAGE / "legacy" / "import-files" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert legacy["importable"] is False
    assert len(legacy["files"]) == 8
    assert all(item["status"] == "SUPERSEDED" for item in legacy["files"])
    assert all(item["importable"] is False for item in legacy["files"])
