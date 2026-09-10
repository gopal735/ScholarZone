"""Regression tests for git integrity — ensure deployment-required files are tracked.

These tests catch the class of bugs where a file exists locally but is missing
from the repository, meaning it never reaches the Docker build or deployment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Critical files required for deployment.
# Paths are relative to the backend/ directory.
# ---------------------------------------------------------------------------
CRITICAL_FILES = [
    "Dockerfile",
    ".dockerignore",
    "requirements.txt",
    "start.sh",
    "render.yaml",
    "app/main.py",
    "app/database.py",
    "app/models.py",
    "app/schemas.py",
    "app/seed.py",
]

BACKEND_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def git_tracked_files() -> set[str] | None:
    """Return set of git-tracked files, or None if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        raw_files = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        normalized = set()
        for f in raw_files:
            if f.startswith("backend/"):
                normalized.add(f[len("backend/") :])
            else:
                normalized.add(f)
        return normalized
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


@pytest.fixture(scope="module")
def git_status_porcelain() -> list[str] | None:
    """Return git status --porcelain output lines, or None if git unavailable."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        normalized = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[-1].startswith("backend/"):
                normalized.append(f"{parts[0]} {parts[-1][len('backend/'):]}")
            else:
                normalized.append(line)
        return normalized
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCriticalFilesTrackedInGit:
    """Every deployment-critical file must be tracked in git."""

    @pytest.mark.parametrize("rel_path", CRITICAL_FILES)
    def test_critical_file_tracked(self, rel_path: str, git_tracked_files):
        if git_tracked_files is None:
            pytest.skip("git is not available in this environment")

        assert rel_path in git_tracked_files, (
            f"{rel_path} is not tracked in git. "
            "It will be absent from the Docker build and any deployment."
        )


class TestCriticalFilesExistOnDisk:
    """Every deployment-critical file must physically exist."""

    @pytest.mark.parametrize("rel_path", CRITICAL_FILES)
    def test_critical_file_exists(self, rel_path: str):
        abs_path = BACKEND_DIR / rel_path
        assert abs_path.exists(), (
            f"{rel_path} does not exist on disk at {abs_path}"
        )


class TestNoUntrackedCriticalFiles:
    """No critical file should appear as untracked in git status."""

    def test_no_untracked_critical_files(self, git_status_porcelain):
        if git_status_porcelain is None:
            pytest.skip("git is not available in this environment")

        untracked = {
            line.split()[-1]
            for line in git_status_porcelain
            if line.startswith("??")
        }

        offending = [f for f in CRITICAL_FILES if f in untracked]
        assert not offending, (
            "The following critical files are untracked in git:\n"
            + "\n".join(f"  - {f}" for f in offending)
        )


class TestNoDeletedCriticalFiles:
    """No critical file should be deleted in the working tree (git status 'D')."""

    def test_no_deleted_critical_files(self, git_status_porcelain):
        if git_status_porcelain is None:
            pytest.skip("git is not available in this environment")

        deleted = {
            line.split()[-1]
            for line in git_status_porcelain
            if line.startswith("D")
        }

        offending = [f for f in CRITICAL_FILES if f in deleted]
        assert not offending, (
            "The following critical files are deleted in the working tree:\n"
            + "\n".join(f"  - {f}" for f in offending)
        )
