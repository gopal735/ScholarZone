"""Generate the immutable build-revision artifact.

This runs during the **build**, not at runtime, and it is the only thing allowed
to decide what revision the deployed artefact claims to be.

Why this exists
---------------
``build_revision()`` used to read ``VERCEL_GIT_COMMIT_SHA`` at runtime and return
the first twelve characters. Two things were wrong with that:

* **It was runtime-controlled.** Anything that can set an environment variable at
  runtime - a misconfigured deploy, a stale process, a hand-edited setting -
  could change what the health endpoint claims without changing a line of code.
* **It was truncated.** Twelve characters cannot be compared against a full
  commit SHA, so the deployment gate could never assert equality. It could only
  check a prefix, which is exactly the check that lets the wrong artefact pass.

The rule now is: the build writes the identity into a generated Python module
inside the package, and the running service reads *only* that module.

Fail-closed
-----------
A missing, malformed, or truncated SHA **fails the build**. A build that cannot
prove which commit it is must not produce an artefact at all, because an
artefact that reports ``unknown`` is indistinguishable from a healthy one to a
naive probe. Local development never runs this script, so it is unaffected.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

#: A commit SHA is exactly 40 lowercase hexadecimal characters. Anything else -
#: a 12-character prefix, a branch name, a deployment URL, a label somebody
#: remembered to set - is rejected rather than truncated.
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

TARGET = pathlib.Path(__file__).resolve().parents[1] / "app" / "_build_revision.py"

TEMPLATE = '''\
"""Immutable build identity.

Generated during the build by ``scripts/generate_build_revision.py``.
This file is deliberately not committed: a checked-in revision would be a
claim about a build that never happened.
"""

BUILD_REVISION = {revision!r}
'''


def fail(message: str) -> int:
    print(f"BUILD REVISION ERROR: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sha",
        default=None,
        help="Full 40-character commit SHA. Defaults to VERCEL_GIT_COMMIT_SHA.",
    )
    parser.add_argument(
        "--out",
        default=str(TARGET),
        help=f"Where to write the artifact (default: {TARGET}).",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Local development only: write a development artifact instead of failing.",
    )
    args = parser.parse_args(argv)

    import os

    raw = (args.sha or os.getenv("VERCEL_GIT_COMMIT_SHA") or "").strip()

    if not raw:
        if args.allow_missing:
            _write(args.out, "development")
            return 0
        return fail(
            "no commit SHA was supplied (--sha or VERCEL_GIT_COMMIT_SHA). "
            "Refusing to build an artefact that cannot prove its own identity."
        )

    if not FULL_SHA.match(raw):
        return fail(
            f"{raw!r} is not a full 40-character lowercase commit SHA. "
            "A prefix, a branch name or a deployment URL is not an identity."
        )

    _write(args.out, raw)
    print(f"build revision embedded: {raw}")
    return 0


def _write(out: str, revision: str) -> None:
    path = pathlib.Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(revision=revision), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())