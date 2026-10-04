#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write the immutable build-provenance artefact for a deployment.

Runs at BUILD time, not at request time, so the revision the service reports
cannot be changed afterwards: not by a runtime environment variable, not by a
request header, not by a branch label, not by a deployment URL.

Validation, not normalisation
-----------------------------
The commit id is validated **raw**. ``" ABC... "``, ``"ABC..."`` and a
12-character prefix all fail. Stripping or lower-casing first would turn a
corrupt or hand-written value into a valid identity, which is precisely the
failure this artefact exists to make impossible. The value written is the value
supplied, unchanged.

Contract
--------
* exactly forty lowercase hexadecimal characters - the full commit id;
* anything else - short, long, upper-case, whitespace-padded, branch, tag, URL,
  ``unknown``, ``dev``, ``latest`` - fails the build;
* a missing SHA fails the build. There is no "unknown" production build.

The build-time source is the platform's own record of the commit it built.
``--sha`` exists for local and CI self-tests; it is validated identically and
is never read at runtime.

Usage
-----
    python scripts/write_build_provenance.py                  # Vercel build
    python scripts/write_build_provenance.py --sha <40 hex>   # local / CI
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ARTIFACT = BACKEND / "app" / "build_provenance.json"

sys.path.insert(0, str(BACKEND))

from app.provenance import (  # noqa: E402
    ALLOWED_KEYS,
    SCHEMA,
    is_canonical_sha,
)

#: Build-time inputs in priority order: the platform's record of what it built,
#: then the explicit self-test input. Neither is read at runtime.
SOURCES = ("VERCEL_GIT_COMMIT_SHA", "SCHOLARZONE_BUILD_SHA")

#: Names that are *not* identities. Supplied in place of a SHA, they are called
#: out specifically: "no SHA provided" sends the reader hunting for a missing
#: variable, when the real mistake is offering a moving label.
REJECTED_HINTS = {
    "VERCEL_GIT_COMMIT_REF": "a branch or tag is a moving label, not a commit",
    "VERCEL_GIT_COMMIT_MESSAGE": "a commit message is not an identity",
    "VERCEL_URL": "a deployment URL is not an identity",
    "VERCEL_ENV": "an environment name is not an identity",
}


class BuildProvenanceError(RuntimeError):
    """The build cannot honestly claim a revision."""


def resolve_sha(explicit: str | None = None) -> str:
    """Return the canonical build SHA exactly as supplied, or refuse to build."""
    if explicit is not None:
        candidate, source = explicit, "--sha"
    else:
        candidate, source = "", ""
        for name in SOURCES:
            value = os.environ.get(name)
            if value:
                candidate, source = value, name
                break

    if not candidate:
        for name, why in REJECTED_HINTS.items():
            value = os.environ.get(name) or ""
            if value and not is_canonical_sha(value):
                raise BuildProvenanceError(
                    f"{name}={value!r} was supplied but {why}. A build cannot claim "
                    "a revision it cannot prove."
                )
        raise BuildProvenanceError(
            "no build-time commit SHA was provided. Vercel sets "
            "VERCEL_GIT_COMMIT_SHA for the commit it builds; --sha is for local "
            "and CI self-tests. Refusing to build: a deployment that cannot name "
            "its commit cannot be verified."
        )

    # Raw validation. No strip(), no lower().
    if not is_canonical_sha(candidate):
        raise BuildProvenanceError(
            f"{source}={candidate!r} is not exactly forty lowercase hexadecimal "
            "characters. A short prefix, an upper-case value, a padded value, a "
            "branch, a tag or a URL cannot identify a build, so the build fails "
            "rather than shipping a revision it cannot prove."
        )

    # Returned unchanged: what was supplied is what is written.
    return candidate


def write_artifact(sha: str, path: Path | None = None) -> Path:
    """Write the artefact. Resolved here so a caller may redirect it."""
    target = ARTIFACT if path is None else path
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"git_commit_sha": sha, "schema": SCHEMA}
    assert set(payload) == set(ALLOWED_KEYS)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sha",
        help="exactly forty lowercase hex characters; defaults to "
             "VERCEL_GIT_COMMIT_SHA",
    )
    args = parser.parse_args(argv)

    try:
        sha = resolve_sha(args.sha)
    except BuildProvenanceError as exc:
        # Loud, specific, fatal. The build must not continue.
        print(f"BUILD PROVENANCE FAILURE: {exc}", file=sys.stderr)
        return 1

    path = write_artifact(sha)
    print(f"build provenance: {sha}")
    try:
        shown = path.relative_to(BACKEND.parent)
    except ValueError:
        shown = path  # redirected (a test); logging must never fail a build
    print(f"artifact        : {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())