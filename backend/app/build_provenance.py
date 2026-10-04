"""Build-time provenance for the deployed artefact.

The revision a deployment reports has to describe the artefact that is actually
running. Reading an environment variable at runtime does not achieve that. The
value belongs to the *function's environment*, not to the build that produced
the *code*, and on this platform the two have been observed to disagree: a
preview built from one commit reported a different commit entirely, while the
platform's own deployment metadata recorded the correct one. A runtime
environment variable therefore cannot be treated as proof of what was built.

So the platform identifier is read exactly once, at BUILD time, validated
against the shape of a real commit, and written into an artefact that ships
inside the package. At runtime that artefact is the only source of truth.

Consequences that matter:

* No environment variable can override the reported revision, including a
  previously supported ``SCHOLARZONE_BUILD_REVISION``.
* No request header is consulted, so a caller cannot influence the answer.
* A build on the platform with a missing or malformed commit SHA fails the build
  instead of publishing an identity-free artefact.
* A full 40-character SHA is required internally. Nothing is ever truncated:
  two commits sharing a 12-character prefix would otherwise be indistinguishable.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

#: Written inside the package so it is part of the artefact that ships. A file
#: beside the package would be the first thing a bundler drops.
ARTIFACT = Path(__file__).with_name("build_revision.txt")

#: The development marker. Deliberately not a hex string: a development build
#: must be distinguishable from a deployment by inspection alone.
DEVELOPMENT_MARKER = "dev"

#: A full commit SHA and nothing else. Anchored, lowercase, exactly 40.
FULL_COMMIT_SHA = re.compile(r"\A[0-9a-f]{40}\Z")

#: Vercel sets this to "1" in every build environment.
ON_PLATFORM = "VERCEL"
PLATFORM_COMMIT = "VERCEL_GIT_COMMIT_SHA"


class ProvenanceError(RuntimeError):
    """Raised when the build identity is absent or unusable.

    This is a build-stopping condition on the platform. At runtime it means the
    artefact is corrupt, and the only safe answer is to refuse to name a commit
    rather than name the wrong one.
    """


def on_platform() -> bool:
    """True when running inside a Vercel build."""
    return (os.getenv(ON_PLATFORM) or "").strip() == "1"


def platform_commit_sha() -> str | None:
    """The full commit SHA the platform built, or ``None`` if unusable.

    Accepts only exactly forty lowercase hex characters. A branch name, a short
    SHA, a long SHA, a URL, arbitrary text or an empty string is not an identity.

    Uppercase is **rejected**, not normalised. An earlier version lower-cased the
    input first, on the reasoning that case is a formatting difference rather
    than an identity difference. That was wrong here: this value is compared for
    exact equality against a runtime revision that the release identity gate also
    refuses to accept in any other form. Tolerating a different shape on the way
    in would mean the build contract and the gate contract disagreed about what a
    commit identity looks like, and the disagreement would only surface at
    verification time - after a deployment - rather than at build time.

    Vercel supplies the SHA in lowercase, so refusing uppercase costs nothing in
    practice and removes a class of silent normalisation.
    """
    raw = (os.getenv(PLATFORM_COMMIT) or "").strip()
    return raw if FULL_COMMIT_SHA.match(raw) else None


def is_deployed_sha(value: str) -> bool:
    return bool(FULL_COMMIT_SHA.match(value))


def _write(value: str) -> str:
    ARTIFACT.write_text(f"{value}\n", encoding="utf-8")
    return value


def embed_build_revision() -> str:
    """BUILD TIME. Persist the identity of this build into the artefact.

    On the platform this is strict: no usable commit SHA is a failed build.
    Off the platform it writes the development marker, because a developer's
    machine has no deployment identity to record and refusing to run would only
    mean nobody could run the tests.
    """
    sha = platform_commit_sha()
    if sha is not None:
        return _write(sha)

    if on_platform():
        present = (os.getenv(PLATFORM_COMMIT) or "").strip()
        raise ProvenanceError(
            "Refusing to publish a build with no usable commit identity: "
            f"{PLATFORM_COMMIT}={present!r} is not a full 40-character commit "
            "SHA. A deployment that cannot name the commit it was built from "
            "cannot be verified, and a guess would be worse than a failure."
        )

    return _write(DEVELOPMENT_MARKER)


def read_embedded_revision() -> str:
    """RUNTIME. The revision this artefact was built from.

    Returns a full 40-character SHA, or the development marker. Raises
    ``ProvenanceError`` if the artefact is missing or malformed, because the
    only honest answer to "which commit is this?" when the answer was lost is to
    refuse to answer.

    The value is read verbatim, with no case folding, for the same reason the
    build refuses uppercase: this revision is compared for exact equality by the
    release identity gate, so accepting a differently-shaped value here would
    only defer the disagreement to verification time.
    """
    try:
        raw = ARTIFACT.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise ProvenanceError(
            f"Build artefact {ARTIFACT.name} is missing from the package. The "
            "build step that embeds the commit SHA did not run, so this build "
            "cannot prove what it is."
        ) from error

    if is_deployed_sha(raw):
        return raw
    if raw == DEVELOPMENT_MARKER:
        return DEVELOPMENT_MARKER

    raise ProvenanceError(
        f"Build artefact {ARTIFACT.name} contains {raw!r}, which is neither a "
        "full 40-character commit SHA nor the development marker. Refusing to "
        "report a revision that was not verified."
    )