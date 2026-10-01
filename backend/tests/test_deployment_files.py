"""Deployment files must be plain UTF-8.

Vercel failed the backend build with "could not parse requirements.txt:
Unexpected '\\ufeff' at line 1:1". A BOM is invisible in every editor, survives
copy-paste, and turns a build into a parse error with no useful location, so the
check is made here rather than left to the next deploy.
"""

from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
BOM = b"\xef\xbb\xbf"

# Every file Vercel parses at build time. requirements.txt is not the only
# parser that rejects a BOM: package.json, vercel.json and workflow YAML all
# fail on one too, and a build that stops at the first file hides the rest.
DEPLOYMENT_FILES = [
    "backend/requirements.txt",
    "frontend/package.json",
    "vercel.json",
    "backend/vercel.json",
    "frontend/vercel.json",
]


@pytest.mark.parametrize("relative", DEPLOYMENT_FILES)
def test_no_byte_order_mark(relative):
    path = REPO / relative
    if not path.exists():
        pytest.skip(f"{relative} not present")
    raw = path.read_bytes()
    assert not raw.startswith(BOM), (
        f"{relative} starts with a UTF-8 BOM; Vercel and pip both reject it"
    )


def test_requirements_is_valid_utf8():
    raw = (REPO / "backend" / "requirements.txt").read_bytes()
    raw.decode("utf-8")  # raises on a malformed byte sequence


def test_requirements_still_parses_as_a_list():
    import re

    text = (REPO / "backend" / "requirements.txt").read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    requirements = [line for line in lines if line and not line.startswith("#")]
    assert requirements, "requirements.txt has no entries"

    # A bare package name is valid; only a stray prose line is not. An earlier
    # version of this test demanded a version specifier on every line and
    # rejected the legitimate unpinned "resend".
    pattern = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9._-]*"          # name
        r"(\[[^\]]+\])?"                          # extras
        r"([<>=!~]=?.+)?$"                        # optional specifier
    )
    for line in requirements:
        assert pattern.match(line), f"unparseable line: {line}"


def test_requirements_first_entry_is_the_annotated_doc_pin():
    # Guards the BOM specifically: the failure mode was the FIRST character.
    first = (REPO / "backend" / "requirements.txt").read_text(
        encoding="utf-8"
    ).splitlines()[0]
    assert first.startswith("annotated-doc"), repr(first)


class TestViteBaseIsDerivedFromThePlatform:
    """The base decides every asset URL, so it must not depend on a human.

    This shipped a blank white page: with base left at "/ScholarZone/", Vite
    rewrote the entry script to /ScholarZone/assets/index.js, that path 404s on
    a root domain, and the app rendered nothing at all.
    """

    @pytest.fixture(scope="class")
    def vite_config(self) -> str:
        return (REPO / "frontend" / "vite.config.js").read_text(encoding="utf-8")

    def test_detects_vercel_from_the_platform_variable(self, vite_config):
        assert "process.env.VERCEL" in vite_config, (
            "base must be derived from VERCEL, which the platform sets, not "
            "only from an env var a human has to remember to add"
        )

    def test_explicit_override_is_still_honoured(self, vite_config):
        assert "VITE_DEPLOY_TARGET" in vite_config

    def test_env_is_loaded_from_the_config_directory(self, vite_config):
        # process.cwd() is the service root under a multi-service build, not
        # the frontend directory.
        assert "import.meta.url" in vite_config

    def test_both_bases_are_the_expected_two_values(self, vite_config):
        assert "'/'" in vite_config
        assert "'/ScholarZone/'" in vite_config


class TestIndexHtmlEntryPoint:
    @pytest.fixture(scope="class")
    def index_html(self) -> str:
        return (REPO / "frontend" / "index.html").read_text(encoding="utf-8")

    def test_entry_script_is_an_absolute_source_path(self, index_html):
        # Vite rewrites this using base, so it must start at the site root.
        assert 'src="/src/main.jsx"' in index_html

    def test_mount_point_exists(self, index_html):
        assert 'id="root"' in index_html

    def test_no_bom_and_no_mojibake(self, index_html):
        assert "Â" not in index_html
        assert "Ã©" not in index_html


class TestApiBaseDefaultsSafely:
    def test_service_defaults_to_a_relative_api_path(self):
        service = (REPO / "frontend" / "src" / "services" / "scholarshipService.js").read_text(
            encoding="utf-8"
        )
        # A hardcoded localhost, or a bare import.meta.env access, renders a
        # blank page in the browser and says nothing useful.
        assert "localhost" not in service
        assert "|| '/api'" in service

    def test_admin_service_has_the_same_default(self):
        service = (REPO / "frontend" / "src" / "services" / "adminImageReviewService.js").read_text(
            encoding="utf-8"
        )
        assert "localhost" not in service
        assert "|| '/api'" in service


class TestNoProcessEnvInBrowserCode:
    """Vite does not define process.env, so a reference throws at runtime."""

    @pytest.mark.parametrize(
        "relative",
        [
            "frontend/src/main.jsx",
            "frontend/src/App.jsx",
            "frontend/src/services/scholarshipService.js",
            "frontend/src/services/adminImageReviewService.js",
            "frontend/src/services/canonicalOrigin.js",
            "frontend/src/components/RedirectHandler.jsx",
        ],
    )
    def test_no_process_env(self, relative):
        path = REPO / relative
        if not path.exists():
            pytest.skip(f"{relative} not present")
        source = path.read_text(encoding="utf-8")
        assert "process.env" not in source, (
            f"{relative} references process.env; Vite only defines import.meta.env, "
            "so this throws in the browser and blanks the page"
        )


class TestRouterBasenameFollowsTheDeployTarget:
    """The router has to agree with where the app is served."""

    @pytest.fixture(scope="class")
    def main_jsx(self) -> str:
        return (REPO / "frontend" / "src" / "main.jsx").read_text(encoding="utf-8")

    def test_basename_comes_from_base_url(self, main_jsx):
        assert "import.meta.env.BASE_URL" in main_jsx

    def test_basename_is_not_a_hardcoded_path(self, main_jsx):
        # A literal '/ScholarZone' told the router it lived one directory deep
        # on a root domain, so no route matched and the page rendered nothing.
        assert 'basename="/ScholarZone"' not in main_jsx

    def test_render_is_wrapped_in_an_error_boundary(self, main_jsx):
        assert "AppErrorBoundary" in main_jsx

    def test_error_boundary_component_exists(self):
        boundary = REPO / "frontend" / "src" / "components" / "AppErrorBoundary.jsx"
        assert boundary.exists()
        source = boundary.read_text(encoding="utf-8")
        # Without componentDidCatch and getDerivedStateFromError this renders
        # nothing and is not an error boundary at all.
        assert "componentDidCatch" in source
        assert "getDerivedStateFromError" in source