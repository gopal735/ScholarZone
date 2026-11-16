import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _mock_resp(status=200, data=None, raw=None):
    class MockResp:
        def __init__(self):
            self.status = status
            self._raw = raw if raw is not None else (json.dumps(data).encode() if data is not None else b"")
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return self._raw
        def decode(self, *a, **k):
            return self._raw.decode("utf-8", errors="replace")
    return MockResp()


def test_verify_api_malformed_http_200_fails(monkeypatch):
    from scripts import verify_api
    import scripts.verify_api as m

    def fake_open_api_url(url, allowed_loopback_ports, timeout):
        if "country=" in url:
            return _mock_resp(200, raw=b"<html>not json</html>")
        return _mock_resp(200, {"items": [], "pagination": {"total": 0}})

    monkeypatch.setattr(m, "open_api_url", fake_open_api_url)
    os.environ["SCHOLARZONE_API_URL"] = "http://127.0.0.1:8000"
    try:
        assert m.main() != 0
    finally:
        os.environ.pop("SCHOLARZONE_API_URL", None)


def test_verify_final_empty_dataset_fails(monkeypatch):
    from scripts import verify_final
    import scripts.verify_final as m

    page = {"items": [], "pagination": {"total": 0, "total_pages": 1, "page": 1, "page_size": 10}}

    def fake_open_api_url(url, allowed_loopback_ports, timeout):
        return _mock_resp(200, page)

    monkeypatch.setattr(m, "open_api_url", fake_open_api_url)
    os.environ["SCHOLARZONE_API_URL"] = "http://127.0.0.1:8000"
    try:
        assert m.main() != 0
    finally:
        os.environ.pop("SCHOLARZONE_API_URL", None)


def test_verify_final_pagination_metadata_inconsistency_raises(monkeypatch):
    from scripts import verify_final
    import scripts.verify_final as m

    page1 = {"items": [{"id": 1}], "pagination": {"total": 4, "total_pages": 2, "page": 1, "page_size": 2}}
    page2 = {"items": [{"id": 2}], "pagination": {"total": 4, "total_pages": 3, "page": 2, "page_size": 2}}
    pages = [page1, page2]
    idx = {"i": 0}

    def fake_open_api_url(url, allowed_loopback_ports, timeout):
        i = idx["i"]
        idx["i"] += 1
        return _mock_resp(200, pages[i])

    monkeypatch.setattr(m, "open_api_url", fake_open_api_url)
    with pytest.raises(m.PaginationError):
        m._fetch_all_pages("http://127.0.0.1:8000", "/scholarships", allowed_ports={8000}, timeout=10)


def test_verify_final_total_mismatch_fails(monkeypatch):
    from scripts import verify_final
    import scripts.verify_final as m

    page = {"items": [{"id": 1, "name": "A", "country": "Belgium"}],
            "pagination": {"total": 5, "total_pages": 1, "page": 1, "page_size": 10}}

    def fake_open_api_url(url, allowed_loopback_ports, timeout):
        return _mock_resp(200, page)

    monkeypatch.setattr(m, "open_api_url", fake_open_api_url)
    os.environ["SCHOLARZONE_API_URL"] = "http://127.0.0.1:8000"
    try:
        assert m.main() != 0
    finally:
        os.environ.pop("SCHOLARZONE_API_URL", None)


def test_verify_final_duplicate_ids_fail(monkeypatch):
    from scripts import verify_final
    import scripts.verify_final as m

    page = {"items": [{"id": 1, "name": "A", "country": "Belgium"},
                      {"id": 1, "name": "B", "country": "Belgium"}],
            "pagination": {"total": 2, "total_pages": 1, "page": 1, "page_size": 10}}

    def fake_open_api_url(url, allowed_loopback_ports, timeout):
        return _mock_resp(200, page)

    monkeypatch.setattr(m, "open_api_url", fake_open_api_url)
    os.environ["SCHOLARZONE_API_URL"] = "http://127.0.0.1:8000"
    try:
        assert m.main() != 0
    finally:
        os.environ.pop("SCHOLARZONE_API_URL", None)


def test_bulk_preflight_scheduler_health_response_validation(monkeypatch):
    from scripts import bulk_preflight
    import scripts.bulk_preflight as m

    # Empty response should fail
    monkeypatch.setattr(m, "open_api_url", lambda url, allowed_loopback_ports, timeout: _mock_resp(200, raw=b""))
    assert m.check_scheduler("http://127.0.0.1:8000") is False

    # Malformed/unhealthy JSON should fail
    monkeypatch.setattr(m, "open_api_url", lambda url, allowed_loopback_ports, timeout: _mock_resp(200, {"status": "error"}))
    assert m.check_scheduler("http://127.0.0.1:8000") is False

    # Healthy response should pass
    monkeypatch.setattr(m, "open_api_url", lambda url, allowed_loopback_ports, timeout: _mock_resp(200, {"status": "ok"}))
    assert m.check_scheduler("http://127.0.0.1:8000") is True


def test_supervisor_render_cleanup_handles_cancellation():
    import asyncio
    from app.services import supervisor_render as render_module

    class Browser:
        async def close(self):
            await asyncio.sleep(10)

    driver = render_module.PlaywrightRenderDriver()
    driver._browser = Browser()
    driver._playwright = None
    driver._outbound_proxy = None

    async def main():
        task = asyncio.create_task(driver.close())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(main())
    assert driver._browser is None