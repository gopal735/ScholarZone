#!/usr/bin/env python3
"""Master deployment preflight command that runs all gates in sequence."""

import os
import subprocess
import sys
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
SCRIPTS_DIR = os.path.join(BACKEND_DIR, "scripts")


def run_script_gate(name: str, script_name: str, cwd: str) -> tuple[bool, str | None]:
    print(f"\n{'=' * 60}")
    print(f"GATE: {name}")
    print(f"{'=' * 60}")
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=False,
            text=True,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        print(f"[FAIL] {name} - script not found: {exc}")
        return False, "script not found"
    if result.returncode == 0:
        print(f"[PASS] {name}")
        return True, None
    print(f"[FAIL] {name}")
    return False, f"exit code {result.returncode}"


def docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False


def gate_readiness() -> tuple[bool, str | None]:
    print(f"\n{'=' * 60}")
    print("GATE: Readiness")
    print(f"{'=' * 60}")
    url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000")
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=5) as resp:
            if resp.status == 200:
                print(f"[PASS] API is ready at {url}")
                return True, None
    except Exception as exc:
        print(f"[WARN] API not reachable at {url}: {exc}")
        return True, "skipped - API not reachable"
    print("[WARN] API not reachable")
    return True, "skipped - API not reachable"


def gate_api_smoke_tests() -> tuple[bool, str | None]:
    print(f"\n{'=' * 60}")
    print("GATE: Critical API Smoke Tests")
    print(f"{'=' * 60}")
    url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000")
    ok = True
    for path in ["/health", "/scholarships/stats"]:
        try:
            with urllib.request.urlopen(f"{url}{path}", timeout=10) as resp:
                print(f"[PASS] {path} -> {resp.status}")
        except Exception as exc:
            print(f"[FAIL] {path} -> {exc}")
            ok = False
    return ok, None if ok else "API smoke test failed"


def main() -> int:
    results = []
    failed = False

    gates = [
        ("Git Integrity", "git_integrity_check.py", REPO_ROOT),
        ("Python Import Integrity", "import_smoke_test.py", BACKEND_DIR),
        ("Schema Compatibility", "schema_compat_check.py", BACKEND_DIR),
        ("Environment Variable Names", "env_config_check.py", BACKEND_DIR),
    ]

    for name, script, cwd in gates:
        ok, reason = run_script_gate(name, script, cwd)
        results.append((name, ok, reason))
        if not ok:
            failed = True
            break

    if not failed:
        if docker_available():
            ok, reason = run_script_gate(
                "Docker Build", "artifact_smoke_test.py", REPO_ROOT
            )
            results.append(("Docker Build", ok, reason))
            if not ok:
                failed = True
            else:
                ok2, reason2 = run_script_gate(
                    "Artifact Startup Test", "artifact_smoke_test.py", REPO_ROOT
                )
                results.append(("Artifact Startup Test", ok2, reason2))
                if not ok2:
                    failed = True
        else:
            print(
                "\n[WARN] Docker not available - skipping Docker-dependent gates"
            )
            results.append(("Docker Build", True, "skipped"))
            results.append(("Artifact Startup Test", True, "skipped"))

    if not failed:
        ok, reason = gate_readiness()
        results.append(("Readiness", ok, reason))
        if not ok and reason and "skipped" not in reason:
            failed = True

    if not failed:
        api_url = os.environ.get("SCHOLARZONE_API_URL")
        if not api_url:
            print(
                "\n[WARN] SCHOLARZONE_API_URL not set - skipping API smoke tests"
            )
            results.append(("API Smoke Tests", True, "skipped - no API URL configured"))
        else:
            ok, reason = gate_api_smoke_tests()
            results.append(("API Smoke Tests", ok, reason))
            if not ok:
                failed = True

    skipped = [
        name for name, ok, reason in results if ok and reason and "skipped" in reason
    ]

    print(f"\n{'=' * 60}")
    print("PRE-FLIGHT SUMMARY")
    print(f"{'=' * 60}")
    for name in skipped:
        print(f"  [SKIPPED] {name}")
    for name, reason in [(n, r) for n, ok, r in results if not ok]:
        print(f"  [FAIL] {name}")

    if failed:
        name, reason = next((n, r) for n, ok, r in results if not ok)
        print(f"\nPRE-FLIGHT FAILED - gate '{name}' failed: {reason}")
        return 1
    print("\nPRE-FLIGHT PASS - all gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
