"""Decide whether a worktree file can be committed as-is.

Taking the working-tree copy of a file risks reverting another workstream's
already-committed changes if this checkout is based on an older revision. This
lists every line the commit would REMOVE that is not part of the trust-semantics
fix, so that risk is visible rather than assumed.
"""
from __future__ import annotations

import re
import subprocess
import sys

# Lines that belong to the trust-semantics repair. Anything removed that is not
# matched by one of these is a line this commit would delete.
TRUST = re.compile(
    r"verified\s*\?\?|\.verified\s*\|\||s\.verified|scholarship\.verified|"
    r"Every listing has a (verified official source|been checked)|"
    r"Explore verified scholarship opportunities|"
    r"formatNumber\(totalScholarships\)|formatNumber\(verifiedCount\)|"
    r"scholarship-card__signals|display:\s*none",
    re.IGNORECASE,
)

FILES = sys.argv[1:] or [
    "frontend/src/pages/ScholarshipDetailsPage.jsx",
    "frontend/src/components/ScholarshipList.jsx",
    "frontend/src/pages/ScholarshipsPage.jsx",
    "frontend/src/pages/HomePage.jsx",
]


def diff(path):
    out = subprocess.run(
        ["git", "diff", "--", path], capture_output=True
    ).stdout.decode("utf-8", "replace")
    return out.splitlines()


def main() -> int:
    total_risky = 0
    for path in FILES:
        removed = [
            line[1:].strip()
            for line in diff(path)
            if line.startswith("-") and not line.startswith("---")
        ]
        added = [
            line[1:].strip()
            for line in diff(path)
            if line.startswith("+") and not line.startswith("+++")
        ]
        risky = [r for r in removed if r and not TRUST.search(r)]
        total_risky += len(risky)
        print(f"\n=== {path} ===")
        print(f"  removed lines : {len(removed)}   added lines : {len(added)}")
        print(f"  removed lines NOT part of the trust fix : {len(risky)}")
        for line in risky:
            print(f"    RISK  -{line[:120]}")
    print(f"\ntotal risky removals across all files: {total_risky}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())