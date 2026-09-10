"""Regression tests for Docker artifact integrity.

Ensures the build context, Dockerfile, .dockerignore, requirements.txt, and
start.sh are all present and correct so that the Docker image contains all
required application code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dockerignore_text() -> str | None:
    path = BACKEND_DIR / ".dockerignore"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: Dockerfile
# ---------------------------------------------------------------------------

class TestDockerfile:
    """Validate backend/Dockerfile exists and contains required instructions."""

    def test_dockerfile_exists(self):
        path = BACKEND_DIR / "Dockerfile"
        assert path.exists(), "backend/Dockerfile does not exist"

    def test_dockerfile_contains_required_instructions(self):
        path = BACKEND_DIR / "Dockerfile"
        content = path.read_text(encoding="utf-8")

        required = ["FROM", "COPY", "CMD", "HEALTHCHECK", "USER"]
        missing = [instr for instr in required if instr not in content]
        assert not missing, (
            f"Dockerfile is missing required instructions: {missing}"
        )


# ---------------------------------------------------------------------------
# Tests: .dockerignore
# ---------------------------------------------------------------------------

class TestDockerignore:
    """Validate backend/.dockerignore protects the build context."""

    def test_dockerignore_includes_app_code(self, dockerignore_text: str):
        if dockerignore_text is None:
            pytest.fail("backend/.dockerignore does not exist")

        app_exclusion_patterns = ["app/", "app/**", "*/app"]
        excluded = any(
            pattern in dockerignore_text for pattern in app_exclusion_patterns
        )
        assert not excluded, (
            ".dockerignore must NOT exclude the app/ directory or the Docker "
            "image will be missing application code."
        )

    def test_dockerignore_excludes_sensitive_files(self, dockerignore_text: str):
        if dockerignore_text is None:
            pytest.fail("backend/.dockerignore does not exist")

        required_patterns = {
            ".git",
            "__pycache__",
            "*.db",
            ".env",
            ".venv",
        }
        missing = [p for p in required_patterns if p not in dockerignore_text]
        assert not missing, (
            ".dockerignore is missing recommended exclusion patterns: "
            + ", ".join(sorted(missing))
        )


# ---------------------------------------------------------------------------
# Tests: requirements.txt
# ---------------------------------------------------------------------------

class TestRequirementsTxt:
    """Validate backend/requirements.txt exists and is parseable."""

    def test_requirements_txt_exists(self):
        path = BACKEND_DIR / "requirements.txt"
        assert path.exists(), "backend/requirements.txt does not exist"

    def test_requirements_txt_parseable(self):
        path = BACKEND_DIR / "requirements.txt"
        content = path.read_text(encoding="utf-8")

        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert lines, "requirements.txt is empty"

        for line in lines:
            assert line.count("=") <= 2 or ">=" in line or "~=" in line or "<=" in line, (
                f"Suspicious requirements line: {line!r}. "
                "Expected a package==version or PEP 508 specifier."
            )


# ---------------------------------------------------------------------------
# Tests: start.sh
# ---------------------------------------------------------------------------

class TestStartSh:
    """Validate backend/start.sh exists, is executable, and checks DB URL."""

    def test_start_sh_exists(self):
        path = BACKEND_DIR / "start.sh"
        assert path.exists(), "backend/start.sh does not exist"

    def test_start_sh_contains_required_checks(self):
        path = BACKEND_DIR / "start.sh"
        content = path.read_text(encoding="utf-8")

        assert "SCHOLARZONE_DATABASE_URL" in content, (
            "start.sh must validate SCHOLARZONE_DATABASE_URL before starting"
        )


# ---------------------------------------------------------------------------
# Tests: build context
# ---------------------------------------------------------------------------

class TestBuildContext:
    """Ensure the Docker build context includes all required application files."""

    @pytest.mark.parametrize(
        "rel_path",
        [
            "app/main.py",
            "app/database.py",
            "app/models.py",
            "app/schemas.py",
            "app/seed.py",
            "app/core/config.py",
            "app/routers/__init__.py",
            "app/routers/scholarships.py",
            "app/routers/verification.py",
            "app/routers/discovery.py",
            "app/routers/admin_image_review.py",
            "app/routers/admin_dashboard.py",
            "app/services/__init__.py",
            "app/repositories/__init__.py",
            "app/data/__init__.py",
        ],
    )
    def test_build_context_contains_critical_files(self, rel_path: str):
        abs_path = BACKEND_DIR / rel_path
        assert abs_path.exists(), (
            f"Build context is missing required file: {rel_path} "
            f"(expected at {abs_path})"
        )
