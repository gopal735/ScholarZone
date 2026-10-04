"""Runtime build provenance.

The deployed service reports the commit it was built from by reading a file
that was written during the build. Nothing at runtime can change it:

* environment variables are not consulted - including
  ``VERCEL_GIT_COMMIT_SHA`` and ``SCHOLARZONE_BUILD_REVISION``;
* request headers are not consulted;
* a branch, tag, deployment URL or short prefix is not a revision.

This is deliberate. The previous implementation read
``VERCEL_GIT_COMMIT_SHA`` from the environment on every cold start and truncated
it to twelve characters, which meant the reported revision was (a) mutable per
deployment and (b) not the full commit id. A deployment that is healthy on the
wrong commit was therefore reported as a healthy deployment.

Missing artefact
-----------------
In production a missing or malformed artefact is **not** papered over. It reports
:data:`UNPROVEN_BUILD`, which the deployment gate treats as a failure. It does
not raise, because refusing to import would turn a provenance defect into an
outage; serving a clearly-unproven revision keeps the failure visible and
debuggable instead. Locally (``environment != "production"``) with no artefact
built, it reports ``dev``.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

#: The full commit id, and nothing shorter.
FULL_SHA = re.compile(r"[0-9a-f]{40}")

#: Reported when a production build has no valid artefact. Deliberately not
#: "unknown": an unknown revision and a missing provenance record are different
#: problems, and the deployment gate must be able to tell them apart.
UNPROVEN_BUILD = "unproven-build"

#: Reported for a non-production process with no artefact built.
DEV_REVISION = "dev"

ARTIFACT = Path(__file__).resolve().parent / "build_provenance.json"


class BuildProvenanceMissing(RuntimeError):
    """No usable provenance artefact was found."""


def read_artifact(path: Path = ARTIFACT) -> str:
    """Return the exact 40-character SHA recorded at build time.

    Raises :class:`BuildProvenanceMissing` when the artefact is absent,
    unreadable, malformed, or does not hold a full commit id.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BuildProvenanceMissing(f"no build artefact at {path}") from exc

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise BuildProvenanceMissing(f"artefact is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise BuildProvenanceMissing("artefact is not an object")

    sha = payload.get("git_commit_sha")
    if not isinstance(sha, str) or not FULL_SHA.fullmatch(sha.strip().lower()):
        raise BuildProvenanceMissing(
            f"artefact git_commit_sha={sha!r} is not a full 40-character commit id"
        )

    return sha.strip().lower()


@lru_cache(maxsize=1)
def _cached_artifact(path: str) -> str | None:
    try:
        return read_artifact(Path(path))
    except BuildProvenanceMissing:
        return None


def build_revision(environment: str = "production") -> str:
    """The revision this process reports. Full 40-char SHA, or a loud failure.

    ``environment`` is passed in rather than read from settings so this module
    has no import cycle and no configuration dependency.
    """
    sha = _cached_artifact(str(ARTIFACT))
    if sha is not None:
        return sha
    return DEV_REVISION if environment != "production" else UNPROVEN_BUILD


def reset_cache() -> None:
    """Forget the memoised value (tests rewrite the artefact in place)."""
    _cached_artifact.cache_clear()