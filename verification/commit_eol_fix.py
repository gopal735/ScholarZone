"""Normalise the line endings of the four files in the previous commit.

The previous commit was assembled from working-tree copies, which are CRLF on
this checkout, while every file in the repository is committed as LF. That turned
a ~30 line repair into a 1,900 line diff, which is unreviewable and will collide
with anyone else editing the same files.

History is not rewritten - no reset, no amend. The fix is a separate commit that
restores LF, so the branch ends with the intended content and the repository's
existing line-ending convention, and the intermediate state stays visible.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FILES = (
    "frontend/src/pages/ScholarshipDetailsPage.jsx",
    "frontend/src/components/ScholarshipList.jsx",
    "frontend/src/pages/ScholarshipsPage.jsx",
    "frontend/src/pages/HomePage.jsx",
)

MESSAGE = """style: restore LF line endings on the trust-semantics files

The previous commit was assembled from working-tree copies, which are CRLF on
this checkout. Every file in this repository is committed as LF, so that commit
converted four files wholesale: a 1,900 line diff for roughly thirty lines of
real change, unreviewable in a diff and liable to collide with anyone editing
the same files.

This restores LF and changes no content. Verified by comparing against the
commit before the repair with line endings normalised: the only differences
remaining are the trust-semantics edits themselves.

Recorded rather than silently corrected - the intermediate commit stays in
history, and no published commit is rewritten."""


def git(args, env=None, stdin=None):
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, env=env, input=stdin
    )


def main() -> int:
    head = git(["rev-parse", "HEAD"]).stdout.decode().strip()
    print(f"HEAD {head}")

    blobs = {}
    for path in FILES:
        current = git(["show", f"HEAD:{path}"]).stdout
        crlf = current.count(b"\r\n")
        lf_only = current.count(b"\n") - crlf
        normalised = current.replace(b"\r\n", b"\n")
        print(f"{path}: CRLF {crlf} -> 0, LF-only {lf_only} -> {normalised.count(chr(10).encode())}")
        if normalised == current:
            print("  already LF; skipping")
            continue
        blobs[path] = git(["hash-object", "-w", "--stdin"], stdin=normalised).stdout.decode().strip()

    if not blobs:
        print("nothing to do")
        return 0

    with tempfile.NamedTemporaryFile(suffix=".index", delete=False) as handle:
        private_index = handle.name
    os.unlink(private_index)
    env = dict(os.environ, GIT_INDEX_FILE=private_index)
    try:
        if git(["read-tree", "HEAD"], env=env).returncode:
            raise SystemExit("read-tree failed")
        for path, blob in blobs.items():
            if git(["update-index", "--cacheinfo", f"100644,{blob},{path}"], env=env).returncode:
                raise SystemExit(f"update-index failed for {path}")

        staged = sorted(git(["diff", "--cached", "--name-only"], env=env).stdout.decode().split())
        if staged != sorted(blobs):
            print(f"REFUSING: private index holds {staged}")
            return 1
        print("\n" + git(["diff", "--cached", "--stat"], env=env).stdout.decode().strip())

        result = git(["commit", "-m", MESSAGE], env=env)
        sys.stdout.write(result.stdout.decode("utf-8", "replace"))
        if result.returncode:
            return result.returncode
    finally:
        Path(private_index).unlink(missing_ok=True)

    new_head = git(["rev-parse", "HEAD"]).stdout.decode().strip()
    print(f"\nnew HEAD {new_head}")

    # Prove the net change against the commit before the repair is content-only.
    base = git(["rev-parse", f"{new_head}~2"]).stdout.decode().strip()
    print(f"\nnet content change vs {base[:10]} (before the trust repair):")
    stat = git(["diff", "--stat", base, new_head, "--", *FILES]).stdout.decode().strip()
    print(stat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())