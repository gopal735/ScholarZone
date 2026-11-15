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


def test_extract_items_and_total_handles_multiple_formats():
    """Test that _extract_items_and_total handles various API response formats."""
    from scripts.verify_api import _extract_items_and_total

    # Format 1: items + pagination.total
    data1 = {"items": [{"id": 1}, {"id": 2}], "pagination": {"total": 100}}
    items, total = _extract_items_and_total(data1)
    assert items == [{"id": 1}, {"id": 2}]
    assert total == 100

    # Format 2: scholarships + total
    data2 = {"scholarships": [{"id": 1}], "total": 50}
    items, total = _extract_items_and_total(data2)
    assert items == [{"id": 1}]
    assert total == 50

    # Format 3: items + total
    data3 = {"items": [{"id": 1}], "total": 25}
    items, total = _extract_items_and_total(data3)
    assert items == [{"id": 1}]
    assert total == 25

    # Format 4: results + count
    data4 = {"results": [{"id": 1}, {"id": 2}], "count": 75}
    items, total = _extract_items_and_total(data4)
    assert items == [{"id": 1}, {"id": 2}]
    assert total == 75

    # Unknown format - empty list, no total
    data5 = {"unknown": "format"}
    items, total = _extract_items_and_total(data5)
    assert items == []
    assert total is None

    # Empty list in known key
    data6 = {"items": [], "total": 0}
    items, total = _extract_items_and_total(data6)
    assert items == []
    assert total == 0


# ============================================================
# verify_final.py regression tests
# ============================================================


def test_verify_final_pagination_across_multiple_pages(monkeypatch):
    """Test that verify_final correctly fetches all pages when there are
    more records than the default page limit."""
    from scripts import verify_final
    import json

    # Create mock data with 3 pages, 2 items per page = 6 total
    page1 = {
        "items": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}],
        "pagination": {"total": 6, "total_pages": 3, "page": 1, "page_size": 2}
    }
    page2 = {
        "items": [{"id": 3, "name": "Item 3"}, {"id": 4, "name": "Item 4"}],
        "pagination": {"total": 6, "total_pages": 3, "page": 2, "page_size": 2}
    }
    page3 = {
        "items": [{"id": 5, "name": "Item 5"}, {"id": 6, "name": "Item 6"}],
        "pagination": {"total": 6, "total_pages": 3, "page": 3, "page_size": 2}
    }
    page4 = {"items": [], "pagination": {"total": 6, "total_pages": 3, "page": 4, "page_size": 2}}

    pages = [page1, page2, page3, page4]
    page_index = 0

    def mock_open_api_url(url, allowed_loopback_ports, timeout):
        nonlocal page_index
        class MockResp:
            def __init__(self, data):
                self._data = data
                self.status = 200
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return json.dumps(self._data).encode()
            def decode(self):
                return json.dumps(self._data)
        if page_index >= len(pages):
            raise AssertionError("Too many page requests")
        data = pages[page_index]
        page_index += 1
        return MockResp(data)

    import scripts.verify_final as verify_final_module
    monkeypatch.setattr(verify_final_module, "open_api_url", mock_open_api_url)

    # Test _fetch_all_pages
    items, pagination = verify_final_module._fetch_all_pages(
        "http://127.0.0.1:8000", "/scholarships", allowed_ports={8000}, timeout=10
    )

    assert len(items) == 6
    assert items[0]["id"] == 1
    assert items[-1]["id"] == 6
    assert pagination is not None
    assert pagination["total"] == 6
    assert pagination["total_pages"] == 3


# ============================================================
# web_search_dry_run.py regression tests
# ============================================================


def test_web_search_dry_run_zero_results_no_division_by_zero():
    """Test that web_search_dry_run handles zero results without division by zero."""
    import sys
    from pathlib import Path
    BACKEND_DIR = Path(__file__).resolve().parents[1]
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from scripts.web_search_dry_run import _print_summary
    import io
    import sys

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        # Call with zero results - should not raise ZeroDivisionError
        results = []
        _print_summary(results)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    # Should not crash and should show N/A for percentages
    assert "Total scholarships processed : 0" in output
    assert "N/A" in output  # Percentages should show N/A, not crash

