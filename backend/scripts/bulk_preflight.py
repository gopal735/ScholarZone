#!/usr/bin/env python3
"""Lightweight preflight before any large autonomous operation."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.parse import urljoin

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.local_smoke_http import open_api_url  # noqa: E402


ALLOWED_LOOPBACK_PORTS = {8000}


def run_check(name: str, cmd: list[str], cwd: str | None = None) -> bool:
    print(f"\n--- {name} ---")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or BACKEND_DIR,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode == 0:
        print(f"[PASS] {name}")
        return True
    print(f"[FAIL] {name}")
    return False


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def check_health(base_url: str) -> bool:
    try:
        with open_api_url(
            _join_url(base_url, "/health"),
            allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
            timeout=10,
        ) as resp:
            if resp.status == 200:
                print("[PASS] Backend healthy (/health = 200)")
                return True
            print(f"[FAIL] Backend returned {resp.status}")
            return False
    except Exception as exc:
        print(f"[FAIL] Backend not reachable: {exc}")
        return False


def check_scheduler(base_url: str) -> bool:
    try:
        with open_api_url(
            _join_url(base_url, "/internal/verify/status"),
            allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
            timeout=10,
        ) as resp:
            if resp.status != 200:
                print(f"[FAIL] Scheduler returned HTTP {resp.status}")
                return False
            data = resp.read().decode("utf-8", errors="replace")
            print(f"[PASS] Scheduler available ({data[:120]})")
            return True
    except Exception as exc:
        print(f"[FAIL] Scheduler check failed: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk operation preflight")
    parser.add_argument(
        "--url",
        default=os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000"),
        help="API base URL",
    )
    args = parser.parse_args()

    print(f"BULK PREFLIGHT - target: {args.url}")
    ok = True

    ok &= check_health(args.url)
    ok &= check_scheduler(args.url)
    ok &= run_check(
        "Schema Compatibility",
        [sys.executable, "scripts/schema_compat_check.py"],
    )
    ok &= run_check(
        "Environment Config",
        [sys.executable, "scripts/env_config_check.py"],
    )

    if ok:
        print("\nBULK PREFLIGHT: PASS")
        return 0
    print("\nBULK PREFLIGHT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())

