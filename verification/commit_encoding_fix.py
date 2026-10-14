"""Commit the single-byte encoding repair with a private git index.

The shared index currently holds another workstream's staged files. Using it
would sweep those into this commit, so the commit is assembled in a throwaway
index built from HEAD: one path, one blob, nothing else.

The blob is HEAD's own ``HomePage.jsx`` with the mis-encoded byte replaced. It
is deliberately NOT the working-tree copy of that file, which belongs to another
workstream and carries unrelated edits.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TARGET = "frontend/src/pages/HomePage.jsx"
BAD = b"\x97"          # cp1252 em dash, written into a UTF-8 file
GOOD = b"\xe2\x80\x94"  # the same character, correctly encoded

MESSAGE = """fix: repair a mis-encoded byte that fails the production build

`frontend/src/pages/HomePage.jsx` carried a single cp1252 em-dash byte (0x97)
inside a UTF-8 file. Rolldown refuses to parse the module, so the Vercel
frontend build aborted with UNLOADABLE_DEPENDENCY and every production deploy
since the list-shape work landed has failed. Two consecutive deploys errored on
this and nothing else.

The committed file is scanned and repaired rather than the working-tree copy:
this is the only invalid-UTF-8 file in the tree, and the working-tree version
belongs to another workstream and carries unrelated edits.

The replacement byte is the UTF-8 encoding of the same em dash, so the rendered
character is identical and no content changes. Verified by extracting HEAD,
applying only this byte, and running the real Vite build: exit 0.

Committed through a private index so another workstream's staged files are not
swept in."""


def git(args, env=None, **kw):
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, env=env, **kw
    )


def main() -> int:
    head = git(["rev-parse", "HEAD"]).stdout.decode().strip()
    print(f"HEAD {head}")

    original = git(["show", f"HEAD:{TARGET}"]).stdout
    try:
        original.decode("utf-8")
        print("HEAD is already valid UTF-8; nothing to commit")
        return 0
    except UnicodeDecodeError as exc:
        print(f"invalid UTF-8 at byte {exc.start}")

    count = original.count(BAD)
    if count != 1:
        print(f"refusing: expected exactly one {BAD!r} byte, found {count}")
        return 1
    fixed = original.replace(BAD, GOOD)
    fixed.decode("utf-8")

    with tempfile.NamedTemporaryFile(suffix=".index", delete=False) as handle:
        private_index = handle.name
    os.unlink(private_index)

    env = dict(os.environ, GIT_INDEX_FILE=private_index)
    try:
        read = git(["read-tree", "HEAD"], env=env)
        if read.returncode:
            print(read.stderr.decode())
            return 1

        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=REPO,
            input=fixed,
            capture_output=True,
            env=env,
        ).stdout.decode().strip()
        print(f"repaired blob {blob}")

        update = git(
            ["update-index", "--cacheinfo", f"100644,{blob},{TARGET}"], env=env
        )
        if update.returncode:
            print(update.stderr.decode())
            return 1

        staged = git(["diff", "--cached", "--name-only"], env=env).stdout.decode().split()
        print(f"paths staged in the PRIVATE index: {staged}")
        if staged != [TARGET]:
            print("refusing: the private index is not scoped to the one file")
            return 1

        stat = git(["diff", "--cached", "--stat"], env=env).stdout.decode().strip()
        print(stat)

        commit = git(["commit", "-m", MESSAGE], env=env)
        sys.stdout.write(commit.stdout.decode())
        sys.stderr.write(commit.stderr.decode())
        if commit.returncode:
            return commit.returncode
    finally:
        Path(private_index).unlink(missing_ok=True)

    new_head = git(["rev-parse", "HEAD"]).stdout.decode().strip()
    print(f"\nnew HEAD {new_head}")

    # The shared index must be exactly as it was.
    shared = git(["diff", "--cached", "--name-only"]).stdout.decode().split()
    print(f"shared index still holds {len(shared)} staged paths (untouched)")
    show = git(["show", "--stat", "--format=", new_head]).stdout.decode().strip()
    print(f"\ncommit contents:\n{show}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())