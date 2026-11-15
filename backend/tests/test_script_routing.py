import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_script(script_rel: str, *args: str, cwd: Path | None = None):
    script = BACKEND_DIR / script_rel
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd or BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_bulk_preflight_supports_direct_execution_from_backend_dir(tmp_path):
    # Direct execution should not fail with "No module named 'scripts'"; may fail later due to unreachable API.
    result = _run_script("scripts/bulk_preflight.py", "--url", "http://127.0.0.1:9", cwd=BACKEND_DIR)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert "No module named 'scripts'" not in combined


def test_preflight_supports_direct_execution_from_backend_dir():
    # Direct execution should reach gate logic/bootstrap; it may fail/skip depending on environment.
    env = os.environ.copy()
    env.pop("SCHOLARZONE_API_URL", None)
    script = BACKEND_DIR / "scripts" / "preflight.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert "No module named 'scripts'" not in combined


def test_verify_api_supports_direct_execution_from_backend_dir():
    # verify_api hardcodes loopback URL; direct execution must not fail on scripts package import bootstrap.
    env = os.environ.copy()
    env["SCHOLARZONE_API_URL"] = "http://127.0.0.1:9"
    script = BACKEND_DIR / "scripts" / "verify_api.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert "No module named 'scripts'" not in combined


def test_verify_final_supports_direct_execution_from_backend_dir():
    env = os.environ.copy()
    env["SCHOLARZONE_API_URL"] = "http://127.0.0.1:9"
    script = BACKEND_DIR / "scripts" / "verify_final.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert "No module named 'scripts'" not in combined


def test_open_api_url_routes_exact_approved_loopback_to_local_adapter(monkeypatch):
    from scripts import local_smoke_http

    calls = {}

    def fake_open_local(url, *, allowed_ports, timeout):
        calls["local"] = (url, allowed_ports, timeout)
        class R:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    def fake_secure_urlopen(*a, **k):
        calls["secure"] = (a, k)
        raise AssertionError("secure_urlopen must not be used for approved loopback")

    monkeypatch.setattr(local_smoke_http, "open_local_smoke_url", fake_open_local)
    monkeypatch.setattr(local_smoke_http, "secure_urlopen", fake_secure_urlopen)

    with local_smoke_http.open_api_url("http://127.0.0.1:8000/health", allowed_loopback_ports={8000}, timeout=3) as resp:
        assert resp.status == 200
    assert calls["local"][0] == "http://127.0.0.1:8000/health"
    assert calls["local"][1] == {8000}


def test_open_api_url_routes_approved_public_https_through_secure_urlopen(monkeypatch):
    from scripts import local_smoke_http

    calls = {}

    def fake_open_local(*a, **k):
        raise AssertionError("loopback adapter must not be used for public https")

    def fake_validate_url(url):
        calls["validated"] = url

    class R:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_secure_urlopen(url, timeout=10.0):
        calls["secure"] = (url, timeout)
        return R()

    monkeypatch.setattr(local_smoke_http, "open_local_smoke_url", fake_open_local)
    monkeypatch.setattr(local_smoke_http.DEFAULT_POLICY, "validate_url", fake_validate_url)
    monkeypatch.setattr(local_smoke_http, "secure_urlopen", fake_secure_urlopen)

    with local_smoke_http.open_api_url("https://api.example.com/health", allowed_loopback_ports={8000}, timeout=7) as resp:
        assert resp.status == 200
    assert calls["validated"] == "https://api.example.com/health"
    assert calls["secure"] == ("https://api.example.com/health", 7)


def test_open_api_url_rejects_non_loopback_http_and_unapproved_targets():
    from scripts import local_smoke_http
    from app.services.outbound_security import UnsafeOutboundTarget

    with pytest.raises(UnsafeOutboundTarget):
        local_smoke_http.open_api_url("http://example.com/health", allowed_loopback_ports={8000})
    with pytest.raises(UnsafeOutboundTarget):
        local_smoke_http.open_api_url("http://127.0.0.1:9000/health", allowed_loopback_ports={8000})
    with pytest.raises(UnsafeOutboundTarget):
        local_smoke_http.open_api_url("ftp://127.0.0.1:8000/health", allowed_loopback_ports={8000})

