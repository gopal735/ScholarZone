#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write the immutable build-provenance artefact for a deployment.

This runs at BUILD time, not at request time, so the revision the service
reports cannot be changed by anything that happens afterwards: not a runtime
environment variable, not a request header, not a branch label, and not a
deployment URL.

Why a file and not the runtime environment
------------------------------------------
``VERCEL_GIT_COMMIT_SHA`` describes what Vercel *built*, and it is trustworthy
for exactly as long as nobody can set it per-deployment. Reading it at runtime
means the reported revision is whatever the environment says, which is the
failure this artefact exists to make impossible: a process can be told what
revision to claim while serving older code. Baking the value into the bundle at
build time removes that possibility, because there is nothing left to change.

Contract
--------
* The SHA must be exactly 40 hexadecimal characters - the full commit id.
* A 12-character prefix is NOT a revision. Neither is a branch, a tag, ``unknown``
  or a URL. Anything but a full SHA is a build failure, never a warning.
* A missing SHA is a build failure. There is no "unknown" production build.

Local and CI use ``--sha`` or ``SCHOLARZONE_BUILD_SHA`` so the self-test can
prove the chain without a Vercel build. Neither is read at runtime.

Usage
-----
    python scripts/write_build_provenance.py                 # Vercel build
    python scripts/write_build_provenance.py --sha <40 hex>  # local / CI
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ARTIFACT = BACKEND / "app" / "build_provenance.json"

#: The full commit id. Anything shorter is a prefix, not an identity.
FULL_SHA = re.compile(r"[0-9a-f]{40}")

#: Build-time inputs, in priority order. The first is the platform's own record
#: of what it built; the second exists so CI can drive the self-test.
SOURCES = ("VERCEL_GIT_COMMIT_SHA", "SCHOLARZONE_BUILD_SHA")

REJECTED_HINTS = {
    "VERCEL_GIT_COMMIT_REF": "a branch or tag is a moving label, not a commit",
    "VERCEL_GIT_COMMIT_MESSAGE": "a message is not an identity",
    "VERCEL_URL": "a deployment URL is not an identity",
    "VERCEL_ENV": "an environment name is not an identity",
}


class BuildProvenanceError(RuntimeError):
    """The build cannot honestly claim a revision."""


def resolve_sha(explicit: str | None = None) -> str:
    """Return the full 40-character build SHA, or refuse to build."""
    if explicit is not None:
        candidate, source = explicit.strip(), "--sha"
    else:
        candidate, source = "", ""
        for name in SOURCES:
            raw = (os.environ.get(name) or "").strip()
            if raw:
                candidate, source = raw, name
                break

    if not candidate:
        # A branch or tag was offered instead of a commit. Say so specifically:
        # "no SHA provided" sends the reader looking for a missing variable,
        # when the real mistake is supplying a moving label.
        for name, why in REJECTED_HINTS.items():
            raw = (os.environ.get(name) or "").strip()
            if raw and not FULL_SHA.fullmatch(raw):
                raise BuildProvenanceError(
                    f"{name}={raw!r} was supplied but {why}. A build cannot "
                    "claim a revision it cannot prove."
                )
        raise BuildProvenanceError(
            "no build-time commit SHA was provided. Set VERCEL_GIT_COMMIT_SHA "
            "(Vercel sets this for the commit it builds) or pass --sha for a "
            "local build. Refusing to build: a deployment that cannot name its "
            "commit cannot be verified."
        )

    if not FULL_SHA.fullmatch(candidate):
        detail = REJECTED_HINTS.get(source, "")
        extra = f" ({detail})" if detail else ""
        raise BuildProvenanceError(
            f"{source}={candidate!r} is not a full 40-character commit SHA"
            f"{extra}. A short prefix, a branch, a tag or a URL cannot identify "
            "a build, so the build fails rather than shipping a revision it "
            "cannot prove."
        )

    return candidate.lower()


def write_artifact(sha: str, path: Path | None = None) -> Path:
    # Resolved here rather than as a default argument, so a caller (or a test)
    # can redirect the artefact by patching this module's ARTIFACT.
    target = ARTIFACT if path is None else path
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "git_commit_sha": sha,
        "schema": "build-provenance/1",
    }
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sha",
        help="full 40-character commit SHA; defaults to VERCEL_GIT_COMMIT_SHA",
    )
    args = parser.parse_args(argv)

    try:
        sha = resolve_sha(args.sha)
    except BuildProvenanceError as exc:
        # Loud, specific, and fatal: the build must not continue.
        print(f"BUILD PROVENANCE FAILURE: {exc}", file=sys.stderr)
        return 1

    path = write_artifact(sha)
    print(f"build provenance: {sha}")
    try:
        shown = path.relative_to(BACKEND.parent)
    except ValueError:
        # The artefact was redirected (a test, or an unusual build layout).
        # Logging must never be the reason a build fails.
        shown = path
    print(f"artifact        : {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())