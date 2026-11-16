#!/usr/bin/env python3
"""Master deployment preflight command that runs all gates in sequence."""

from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import urljoin

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
SCRIPTS_DIR = os.path.join(BACKEND_DIR, "scripts")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.local_smoke_http import open_api_url  # noqa: E402


ALLOWED_LOOPBACK_PORTS = {8000}


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


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def gate_readiness() -> tuple[bool, str | None]:
    print(f"\n{'=' * 60}")
    print("GATE: Readiness")
    print(f"{'=' * 60}")
    # Use port 8001 to match artifact_smoke_test.py which runs the container on port 8001
    url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8001")
    try:
        with open_api_url(
            _join_url(url, "/health"),
            allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
            timeout=5,
        ) as resp:
            if resp.status == 200:
                print(f"[PASS] API is ready at {url}")
                return True, None
            else:
                print(f"[FAIL] API returned status {resp.status} at {url}")
                return False, f"API returned status {resp.status}"
    except Exception as exc:
        print(f"[FAIL] API not reachable at {url}: {exc}")
        return False, f"API not reachable: {exc}"


def gate_api_smoke_tests() -> tuple[bool, str | None]:
    print(f"\n{'=' * 60}")
    print("GATE: Critical API Smoke Tests")
    print(f"{'=' * 60}")
    # Use port 8001 to match artifact_smoke_test.py which runs the container on port 8001
    url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8001")
    ok = True
    for path in ["/health", "/scholarships/stats"]:
        try:
            with open_api_url(
                _join_url(url, path),
                allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
                timeout=10,
            ) as resp:
                if 200 <= resp.status < 300:
                    print(f"[PASS] {path} -> {resp.status}")
                else:
                    print(f"[FAIL] {path} -> {resp.status}")
                    ok = False
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

