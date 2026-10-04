"""Runtime build provenance.

The deployed service reports the commit it was built from by reading a file
written during the build. Nothing at runtime can change it.

Identity is **validated, never normalised.** A canonical commit id is already
canonical: it is exactly forty lowercase hexadecimal characters. Stripping or
lower-casing before validating would let a corrupted or hand-written value
become a valid identity, which is the failure this whole mechanism exists to
prevent. So an artefact carrying ``" ABC... "`` or an upper-case SHA is
**rejected**, not repaired.

The service therefore must never report healthy while its build identity is
unproven: ``/health`` returns 503 in production unless a valid artefact exists
(see :func:`artifact_state`).

Missing artefact
----------------
Development without a built artefact reports ``dev`` so local work stays
usable. **Production** reports :data:`UNPROVEN_BUILD`, and ``/health`` fails
closed with 503. It never reports ``unknown``, ``latest`` or a fabricated
identity, and it never falls back to an environment variable.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

#: The one canonical identity rule, shared by the generator, the artefact
#: reader and the release gate: exactly forty lowercase hex characters.
#:
#: Anchored so it cannot be satisfied by a substring, and applied with
#: ``fullmatch`` so surrounding characters - including whitespace - fail.
CANONICAL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")

#: Reported when a production build has no usable artefact. Deliberately not a
#: SHA and never paired with HTTP 200: the deployment gate rejects it, and
#: ``/health`` fails closed.
UNPROVEN_BUILD = "unproven-build"

#: Reported for a non-production process with no artefact built.
DEV_REVISION = "dev"

ARTIFACT = Path(__file__).resolve().parent / "build_provenance.json"

SCHEMA = "build-provenance/1"

#: Exact accepted artefact structure. Any additional key is a malformed
#: artefact rather than something to ignore, so a future writer cannot smuggle
#: a second, ambiguous identity field in beside the real one.
ALLOWED_KEYS = frozenset({"git_commit_sha", "schema"})


class BuildProvenanceMissing(RuntimeError):
    """No usable provenance artefact was found."""


class BuildProvenanceMalformed(BuildProvenanceMissing):
    """An artefact exists but does not carry exactly one canonical identity."""


def is_canonical_sha(value) -> bool:
    """True only for exactly forty lowercase hex characters.

    No stripping, no case folding. This is the single definition of a valid
    identity used across build, runtime and release verification.
    """
    return isinstance(value, str) and CANONICAL_SHA.fullmatch(value) is not None


def read_artifact(path: Path = ARTIFACT) -> str:
    """Return the exact 40-character SHA recorded at build time.

    Raises :class:`BuildProvenanceMalformed` for anything that is not exactly
    one canonical identity in exactly the accepted structure, and
    :class:`BuildProvenanceMissing` when there is no artefact at all.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BuildProvenanceMissing(f"no build artefact at {path}") from exc

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise BuildProvenanceMalformed(f"artefact is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise BuildProvenanceMalformed("artefact is not a JSON object")

    extra = set(payload) - ALLOWED_KEYS
    if extra:
        raise BuildProvenanceMalformed(
            f"artefact carries unexpected field(s) {sorted(extra)}; an ambiguous "
            "identity must not be tolerated"
        )

    if payload.get("schema") != SCHEMA:
        raise BuildProvenanceMalformed(
            f"artefact schema {payload.get('schema')!r} is not {SCHEMA!r}"
        )

    sha = payload.get("git_commit_sha")
    if not is_canonical_sha(sha):
        raise BuildProvenanceMalformed(
            "artefact git_commit_sha is not exactly forty lowercase hex characters"
        )
    return sha


@lru_cache(maxsize=1)
def _cached_artifact(path: str):
    try:
        return read_artifact(Path(path)), None
    except BuildProvenanceMissing as exc:
        return None, str(exc)


def artifact_state(environment: str = "production"):
    """Return ``(revision, error)`` for the current artefact.

    ``revision`` is a canonical 40-character SHA, or ``dev`` in development
    without an artefact. ``error`` is a human-readable reason whenever the
    identity is not proven. Callers must treat a non-empty ``error`` as
    unhealthy in production.
    """
    sha, error = _cached_artifact(str(ARTIFACT))
    if sha is not None:
        return sha, None
    if environment != "production":
        return DEV_REVISION, error
    return UNPROVEN_BUILD, error


def build_revision(environment: str = "production") -> str:
    """The revision this process reports. Never fabricated, never truncated."""
    revision, _error = artifact_state(environment)
    return revision


def reset_cache() -> None:
    """Forget the memoised value (tests rewrite the artefact in place)."""
    _cached_artifact.cache_clear()