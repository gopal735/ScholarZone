"""Embed the build identity into the artefact. Run at BUILD TIME on Vercel.

The backend service declares this as its ``buildCommand`` in ``vercel.json``, so
Vercel runs it inside the build with ``VERCEL_GIT_COMMIT_SHA`` set to the commit
it is compiling. The value is validated and written into
``app/build_revision.txt``, which ships inside the deployed package.

Exit status is the contract: non-zero fails the build. That is the entire point
- a build that cannot name its commit must not become a healthy deployment.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.build_provenance import (  # noqa: E402
    DEVELOPMENT_MARKER,
    ProvenanceError,
    embed_build_revision,
    on_platform,
)


def main() -> int:
    try:
        value = embed_build_revision()
    except ProvenanceError as error:
        print(f"BUILD FAILED: {error}", file=sys.stderr)
        return 1

    where = "platform build" if on_platform() else "local development"
    label = value if value != DEVELOPMENT_MARKER else f"{DEVELOPMENT_MARKER} (not a deployment)"
    print(f"Build revision embedded for {where}: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())