#!/usr/bin/env python3
"""Ensure deployment-required files are tracked in Git and present in HEAD."""

import os
import subprocess
import sys

REQUIRED_FILES = [
    "backend/app/main.py",
    "backend/app/core/config.py",
    "backend/app/database.py",
    "backend/app/models.py",
    "backend/app/schemas.py",
    "backend/app/seed.py",
    "backend/app/routers/scholarships.py",
    "backend/app/routers/verification.py",
    "backend/app/routers/admin_image_review.py",
    "backend/app/routers/discovery.py",
    "backend/app/routers/admin_dashboard.py",
    "backend/app/services/discovery_scheduler.py",
    "backend/app/services/discovery_pipeline.py",
    "backend/app/services/discovery_config.py",
    "backend/app/services/image_discovery.py",
    "backend/app/services/image_validator.py",
    "backend/app/services/scholarship_image_verifier.py",
    "backend/app/services/scholarship_fetch_executor.py",
    "backend/app/services/scholarship_ingestion.py",
    "backend/app/services/scholarship_updater.py",
    "backend/app/services/scholarship_verifier.py",
    "backend/app/services/lifecycle_manager.py",
    "backend/app/services/telemetry.py",
    "backend/app/services/source_resolver.py",
    "backend/app/services/official_source_fetcher.py",
    "backend/app/services/scholarship_extractor.py",
    "backend/app/services/scholarship_evidence.py",
    "backend/app/services/verification_confidence.py",
    "backend/app/services/scheduler_engine.py",
    "backend/app/services/scheduler_config.py",
    "backend/app/scheduler_v2.py",
    "backend/app/data/verified_scholarships.py",
    "backend/requirements.txt",
    "backend/Dockerfile",
    "backend/start.sh",
    "backend/.dockerignore",
]


def git_ls_files() -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        return set(result.stdout.splitlines())
    except subprocess.CalledProcessError as exc:
        print(f"[FAIL] git ls-files failed: {exc.stderr.strip()}")
        sys.exit(1)


def git_status_porcelain() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line for line in result.stdout.splitlines() if line.startswith("??")]
    except subprocess.CalledProcessError as exc:
        print(f"[FAIL] git status failed: {exc.stderr.strip()}")
        sys.exit(1)


def main() -> int:
    tracked = git_ls_files()
    untracked = git_status_porcelain()
    untracked_paths = {line[3:].strip() for line in untracked}

    all_ok = True
    for path in REQUIRED_FILES:
        if not os.path.exists(path):
            print(f"[FAIL] MISSING: {path}")
            all_ok = False
        elif path not in tracked:
            print(f"[FAIL] UNTRACKED: {path}")
            all_ok = False
        else:
            print(f"[PASS] {path}")

    if untracked_paths:
        print(f"\nNote: {len(untracked_paths)} untracked file(s) in working tree")

    if all_ok:
        print("\nGIT INTEGRITY: PASS")
        return 0
    print("\nGIT INTEGRITY: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
