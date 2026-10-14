"""Verify the committed tree builds once the single mis-encoded byte is fixed.

The Vercel build reads the committed blob, not the working tree, so proving the
fix requires building the commit. This extracts HEAD into a throwaway directory,
applies only the byte repair, and runs the real frontend build there - leaving
the working tree, which holds another workstream's uncommitted edits, untouched.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP = Path(r"C:\Users\GopaL\AppData\Local\Temp\kilo\vercel-build-check")
TARGET = "frontend/src/pages/HomePage.jsx"

# `npm` on Windows resolves to a PowerShell script, which a subprocess cannot
# execute directly. npm.cmd is the real entry point.
NPM = r"C:\Program Files\nodejs\npm.cmd" if sys.platform == "win32" else "npm"


def run(args, cwd, **kw):
    return subprocess.run(args, cwd=cwd, capture_output=True, **kw)


def text_of(result) -> str:
    """Decode build output as UTF-8, never as the console's code page.

    The default cp1252 codec raises on ordinary UTF-8 build output, which turns
    a build log into a crash.
    """
    return (result.stdout or b"").decode("utf-8", "replace") + (
        result.stderr or b""
    ).decode("utf-8", "replace")


def main() -> int:
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)

    tar_path = TMP / "tree.tar"
    tar_path.write_bytes(run(["git", "archive", rev], REPO).stdout)
    with tarfile.open(tar_path) as tar:
        tar.extractall(TMP)
    tar_path.unlink()

    blob = (TMP / TARGET).read_bytes()
    try:
        blob.decode("utf-8")
        print(f"{rev}: {TARGET} already valid UTF-8")
        repaired = blob
        applied = False
    except UnicodeDecodeError as exc:
        # cp1252 0x97 is an em dash. Re-encoding it to UTF-8 changes the byte
        # sequence and nothing else: the rendered character is identical.
        repaired = blob.replace(b"\x97", b"\xe2\x80\x94")
        applied = True
        print(f"{rev}: {TARGET} had invalid UTF-8 at byte {exc.start}")
        print(f"  repaired bytes : {blob[exc.start-20:exc.start+20]!r}")
        print(f"               -> {repaired[exc.start-20:exc.start+22]!r}")
    (TMP / TARGET).write_bytes(repaired)
    repaired.decode("utf-8")

    # Any other file that would fail the same way is found here rather than as a
    # second failed deploy.
    remaining = []
    for path in (TMP / "frontend" / "src").rglob("*"):
        if path.is_file() and path.suffix in {".js", ".jsx", ".css", ".json"}:
            try:
                path.read_bytes().decode("utf-8")
            except UnicodeDecodeError as exc:
                remaining.append((str(path.relative_to(TMP)), exc.start))
    print(f"other invalid-UTF-8 files under frontend/src: {len(remaining)} {remaining}")

    link = TMP / "frontend" / "node_modules"
    source_modules = REPO / "frontend" / "node_modules"
    if not link.exists() and source_modules.exists():
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(source_modules)],
                check=True,
                capture_output=True,
            )
            print("linked node_modules from the working tree")
        except subprocess.CalledProcessError as exc:
            print("junction failed; falling back to npm ci")
            install = run([NPM, "ci"], TMP / "frontend")
            print(text_of(install)[-800:])

    build = run([NPM, "run", "build"], TMP / "frontend")
    print()
    print(f"=== npm run build on {rev} + encoding fix (applied={applied}) ===")
    print(f"exit code: {build.returncode}")
    tail = text_of(build).strip().splitlines()
    for line in tail[-18:]:
        print("  " + line)
    return build.returncode


if __name__ == "__main__":
    raise SystemExit(main())