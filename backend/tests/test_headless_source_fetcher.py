"""Tests for the headless-browser fallback's decision logic.

The browser must only be used where it could actually change the answer, and a
failed render must never look like a success. These tests pin the decision, not
the browser, so they run without a browser installed.
"""

from __future__ import annotations

import pytest

from app.services.headless_source_fetcher import (
    BrowserFetch,
    HeadlessSourceFetcher,
    should_try_browser,
)


class TestShouldTryBrowser:
    @pytest.mark.parametrize("status", [403, 401, 429, 503, 511])
    def test_bot_management_statuses_are_retried(self, status):
        assert should_try_browser(status, None) is True

    @pytest.mark.parametrize("error", ["forbidden", "timeout", "connection_error", "blocked"])
    def test_transport_errors_are_retried(self, error):
        assert should_try_browser(None, error) is True

    @pytest.mark.parametrize("status", [200, 204, 301, 404, 410, 500])
    def test_real_answers_are_not_retried(self, status):
        """A 404 or a 500 is what the server said; a browser would not help."""
        assert should_try_browser(status, None) is False

    def test_a_dns_failure_is_not_worth_a_browser(self):
        assert should_try_browser(None, "dns_error") is False


class TestBrowserFetchUsability:
    def test_a_thin_body_is_not_a_success(self):
        assert BrowserFetch(url="u", ok=True, html="<html></html>").usable is False

    def test_a_rendered_page_is_usable(self):
        html = "<html><body>" + ("text " * 200) + "</body></html>"
        assert BrowserFetch(url="u", ok=True, html=html).usable is True

    def test_a_failed_render_is_never_usable(self):
        assert BrowserFetch(url="u", ok=False, error="http_403").usable is False


class TestFetcherDisabled:
    def test_disabled_fetcher_refuses_without_launching(self):
        fetcher = HeadlessSourceFetcher(enabled=False)
        assert fetcher.available() is False
        result = fetcher.fetch("https://example.org/")
        assert result.ok is False
        assert result.error == "browser_unavailable"

    def test_close_is_idempotent(self):
        fetcher = HeadlessSourceFetcher(enabled=False)
        fetcher.close()
        fetcher.close()
        # A closed fetcher must not resurrect itself into launching a browser.
        assert fetcher.fetch("https://example.org/").error == "browser_unavailable"
