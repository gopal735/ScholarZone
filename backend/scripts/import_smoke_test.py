#!/usr/bin/env python3
"""Validate that ALL production Python imports resolve correctly against the source tree."""

import importlib
import os
import sys
import traceback

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")
os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///:memory:")

MODULES = [
    "app.main",
    "app.core.config",
    "app.database",
    "app.models",
    "app.schemas",
    "app.seed",
    "app.routers.scholarships",
    "app.routers.verification",
    "app.routers.admin_image_review",
    "app.routers.discovery",
    "app.routers.admin_dashboard",
    "app.services.discovery_scheduler",
    "app.services.discovery_pipeline",
    "app.services.discovery_config",
    "app.services.image_discovery",
    "app.services.image_validator",
    "app.services.scholarship_image_verifier",
    "app.services.scholarship_fetch_executor",
    "app.services.scholarship_ingestion",
    "app.services.scholarship_updater",
    "app.services.scholarship_verifier",
    "app.services.lifecycle_manager",
    "app.services.telemetry",
    "app.services.source_resolver",
    "app.services.official_source_fetcher",
    "app.services.scholarship_extractor",
    "app.services.scholarship_evidence",
    "app.services.verification_confidence",
    "app.services.scheduler_engine",
    "app.services.scheduler_config",
    "app.scheduler_v2",
    "app.data.verified_scholarships",
]


def main() -> int:
    passed = []
    failed = []

    for mod in MODULES:
        try:
            importlib.import_module(mod)
            passed.append(mod)
        except Exception:
            failed.append((mod, traceback.format_exc()))

    for mod in passed:
        print(f"[PASS] {mod}")
    for mod, tb in failed:
        print(f"[FAIL] {mod}")
        print(tb)

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
