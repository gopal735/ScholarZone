#!/usr/bin/env python3
"""Build the production Docker image, start it locally, run smoke tests, and stop it."""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
IMAGE_TAG = "scholarzone:smoke-test"
CONTAINER_NAME = "scholarzone-smoke-test"
SCRIPT_PATH_IN_CONTAINER = "/app/scripts/import_smoke_test.py"


def docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def build_image() -> bool:
    print("Building Docker image...")
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, BACKEND_DIR],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[FAIL] Docker build failed:\n{result.stderr[-2000:]}")
        return False
    print("[PASS] Docker build succeeded")
    return True


def run_container(port: str) -> str | None:
    cmd = [
        "docker", "run", "-d",
        "-p", f"{port}:8000",
        "-e", "SCHOLARZONE_ENVIRONMENT=test",
        "-e", "SCHOLARZONE_DATABASE_URL=sqlite:///tmp/smoke_test.db",
        "--name", CONTAINER_NAME,
        IMAGE_TAG,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[FAIL] Docker run failed:\n{result.stderr[-2000:]}")
        return None
    container_id = result.stdout.strip()
    print(f"[PASS] Container started: {container_id}")
    return container_id


def wait_for_health(port: str, timeout: int = 60) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    print("[PASS] /health returned 200")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(2)
    print(f"[FAIL] /health did not return 200 within {timeout}s")
    return False


def test_endpoint(port: str, path: str, expected: int = 200) -> bool:
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            if resp.status == expected:
                print(f"[PASS] {path} -> {resp.status}")
                return True
            print(f"[FAIL] {path} -> {resp.status} (expected {expected})")
            return False
    except Exception as exc:
        print(f"[FAIL] {path} -> {exc}")
        return False


def run_container_import_test() -> bool:
    result = subprocess.run(
        ["docker", "exec", CONTAINER_NAME, "python", SCRIPT_PATH_IN_CONTAINER],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("[PASS] Container import smoke test passed")
        return True
    print(f"[FAIL] Container import smoke test failed:\n{result.stdout[-2000:]}")
    if result.stderr:
        print(result.stderr[-2000:])
    return False


def stop_container() -> None:
    subprocess.run(
        ["docker", "rm", "-f", CONTAINER_NAME],
        capture_output=True,
        text=True,
    )


def main() -> int:
    if not docker_available():
        print("Docker is not available. Skipping artifact smoke test.")
        return 2

    if not build_image():
        return 1

    port = "8001"
    container_id = run_container(port)
    if container_id is None:
        return 1

    try:
        if not wait_for_health(port):
            return 1

        ok = True
        ok &= test_endpoint(port, "/health")
        ok &= test_endpoint(port, "/scholarships/stats")
        ok &= run_container_import_test()

        if not ok:
            return 1

        print("\nARTIFACT SMOKE TEST: PASS")
        return 0
    finally:
        stop_container()


if __name__ == "__main__":
    sys.exit(main())
