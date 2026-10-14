"""Commit the trust-semantics fixes with a private git index.

The deployed detail page computes ``isVerified = scholarship.verified ?? true``.
The legacy boolean is true on all 386 public records, so every record - including
the 22 that are ``needs_review`` - renders "Verified listing". That is a false
claim to an applicant, and it is live now.

Four components are committed from the working tree, after checking that every
line the commit removes belongs to this repair. ``Ledger.css`` is NOT taken from
the working tree: it holds another workstream's layout work, and only the one
rule that hides the directory card's verification badge belongs here. That file is
rebuilt from HEAD with that single rule deleted.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Verified above: every removed line in each of these is part of the repair.
WORKTREE_FILES = (
    "frontend/src/pages/ScholarshipDetailsPage.jsx",
    "frontend/src/components/ScholarshipList.jsx",
    "frontend/src/pages/ScholarshipsPage.jsx",
    "frontend/src/pages/HomePage.jsx",
)

# Rebuilt from HEAD rather than taken from the working tree.
LEDGER = "frontend/src/Ledger.css"
BAD_RULE = ".scholarship-grid .scholarship-card__signals"

MESSAGE = """fix: derive every public verification claim from verification_status

The deployed detail page computed

    const isVerified = scholarship.verified ?? true

`verified` is the legacy boolean meaning "a source was inspected at some point".
It is true on all 386 public records and absent on none, so the pill rendered
"Verified listing" for every record - including the 22 whose state is
needs_review, among them all four the audit left unresolved. A record whose
awarding body could not be reached was presented to applicants as verified.

Four surfaces are corrected together, because each was the same mistake in a
different place:

* ScholarshipDetailsPage - the pill now reads verification_status === 'active'.
  Anything else says "Confirm with provider", which is what the record means.
* ScholarshipList - "recommended" compared `verified ?? true` on both sides, so
  the comparison was always zero and the ordering was arbitrary. It now ranks on
  the authoritative state.
* HomePage - the verified figure counted `s.verified ||`, which made it equal
  the catalogue size by another route, and two statistics tiles read the
  paginated directory array instead of the stats endpoint, publishing "100
  Total opportunities" under a trust bar reading 386.
* ScholarshipsPage - meta descriptions asserted "Every listing has a verified
  official source" on the catalogue's behalf, which is precisely the claim the
  card badge deliberately withholds per record.

Ledger.css is rebuilt from HEAD with one rule deleted rather than taken from the
working tree, which holds another workstream's layout work: the rule hid the
directory card's verification badge entirely, so no card published a
verification state at all.

No Match or Count code is touched. No scholarship data is touched."""


def git(args, env=None, stdin=None):
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, env=env, input=stdin
    )


def fail(message, result=None):
    print(f"REFUSING: {message}")
    if result is not None:
        print(result.stderr.decode("utf-8", "replace"))
    raise SystemExit(1)


def strip_badge_rule(css: bytes) -> bytes:
    """Delete the rule that hides the card verification badge, and nothing else."""
    text = css.decode("utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    index = 0
    removed = 0
    while index < len(lines):
        line = lines[index]
        if BAD_RULE in line and line.rstrip().endswith("{"):
            index += 1
            depth = 1
            while index < len(lines) and depth:
                depth += lines[index].count("{") - lines[index].count("}")
                index += 1
            removed += 1
            continue
        out.append(line)
        index += 1
    if removed != 1:
        fail(f"expected exactly one {BAD_RULE!r} rule, found {removed}")
    return "".join(out).encode("utf-8")


def main() -> int:
    head = git(["rev-parse", "HEAD"]).stdout.decode().strip()
    print(f"HEAD {head}")

    blobs: dict[str, str] = {}

    for path in WORKTREE_FILES:
        data = (REPO / path).read_bytes()
        data.decode("utf-8")  # a build-breaking byte must never reach a commit
        blobs[path] = git(["hash-object", "-w", "--stdin"], stdin=data).stdout.decode().strip()
        print(f"worktree blob  {path}  {blobs[path][:10]}")

    head_css = git(["show", f"HEAD:{LEDGER}"]).stdout
    fixed_css = strip_badge_rule(head_css)
    print(f"{LEDGER}: {len(head_css)} -> {len(fixed_css)} bytes, rule removed")
    blobs[LEDGER] = git(["hash-object", "-w", "--stdin"], stdin=fixed_css).stdout.decode().strip()
    print(f"rebuilt blob   {LEDGER}  {blobs[LEDGER][:10]}")

    with tempfile.NamedTemporaryFile(suffix=".index", delete=False) as handle:
        private_index = handle.name
    os.unlink(private_index)
    env = dict(os.environ, GIT_INDEX_FILE=private_index)
    try:
        if git(["read-tree", "HEAD"], env=env).returncode:
            fail("read-tree failed", git(["read-tree", "HEAD"], env=env))

        for path, blob in blobs.items():
            result = git(
                ["update-index", "--cacheinfo", f"100644,{blob},{path}"], env=env
            )
            if result.returncode:
                fail(f"update-index failed for {path}", result)

        staged = sorted(
            git(["diff", "--cached", "--name-only"], env=env).stdout.decode().split()
        )
        print(f"\nprivate index holds {len(staged)} paths:")
        for path in staged:
            print(f"  {path}")
        if staged != sorted([*WORKTREE_FILES, LEDGER]):
            fail(f"private index is not scoped to the intended files: {staged}")

        print("\n" + git(["diff", "--cached", "--stat"], env=env).stdout.decode().strip())

        # The patch that removes the legacy reads must be present.
        patch = git(["diff", "--cached"], env=env).stdout.decode("utf-8", "replace")
        for needle in (
            "scholarship.verified ?? true",
            "s.verified ||",
            BAD_RULE,
        ):
            if needle not in patch:
                fail(f"expected the patch to remove {needle!r}")

        result = git(["commit", "-m", MESSAGE], env=env)
        sys.stdout.write(result.stdout.decode("utf-8", "replace"))
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        if result.returncode:
            return result.returncode
    finally:
        Path(private_index).unlink(missing_ok=True)

    new_head = git(["rev-parse", "HEAD"]).stdout.decode().strip()
    print(f"\nnew HEAD {new_head}")
    print(git(["show", "--stat", "--format=", new_head]).stdout.decode().strip())

    shared = git(["diff", "--cached", "--name-only"]).stdout.decode().split()
    print(f"\nshared index still holds {len(shared)} staged paths (untouched by this commit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())