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