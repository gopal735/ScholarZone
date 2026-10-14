"""Find every tracked file whose committed bytes are not valid UTF-8.

A single mis-encoded byte fails the whole Vercel frontend build, because the
bundler refuses to parse the module it appears in. Finding one file at a time
means one failed deploy per file, so the whole tree is scanned at once.
"""
from __future__ import annotations

import subprocess
import sys

REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

names = subprocess.run(
    ["git", "ls-tree", "-r", "--name-only", REV], capture_output=True, text=True, check=True
).stdout.splitlines()

bad: list[tuple[str, int, int, str]] = []
checked = 0

for name in names:
    if name.startswith(("verification/", "research/", "archive/")) and not name.endswith(
        (".jsx", ".js", ".css", ".json", ".py", ".ts")
    ):
        continue
    blob = subprocess.run(
        ["git", "show", f"{REV}:{name}"], capture_output=True
    ).stdout
    if not blob:
        continue
    checked += 1
    try:
        blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        start = max(0, exc.start - 45)
        window = blob[exc.start : exc.end + 45]
        bad.append((name, exc.start, exc.start - start, window))

print(f"rev {REV}: checked {checked} blobs")
print(f"invalid UTF-8 files: {len(bad)}")
for name, position, _, window in bad:
    print()
    print(f"  {name}  byte {position}")
    print(f"    bytes : {window!r}")
    # 0x97 in cp1252 is an em dash; the same byte in latin-1 is a control char.
    for encoding in ("cp1252", "latin-1"):
        try:
            print(f"    as {encoding:8s}: {window.decode(encoding)!r}")
        except UnicodeDecodeError:
            print(f"    as {encoding:8s}: <undecodable>")
