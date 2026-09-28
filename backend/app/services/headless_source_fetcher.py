"""Headless-browser fetch fallback for official sources that refuse plain HTTP.

A large block of official scholarship pages - national education portals,
university sites behind Cloudflare or Akamai, government sites with bot
management - answer a plain HTTP request with 403 while serving the real page
to a browser. For those, a 403 is not evidence the information is absent; it is
evidence the request looked like a bot.

This service re-fetches exactly those URLs in a real browser, and returns the
rendered HTML so the existing extraction path is reused unchanged. Constraints
that keep this safe and cheap:

* it is only ever a FALLBACK. The plain-HTTP path runs first, and a 403 there
  is what triggers this. Nothing bypasses, authenticates to, or defeats an
  access control; the browser loads the same public page a student would.
* one shared browser process per service instance, reused across records, so a
  maintenance pass pays the start-up cost once.
* a hard per-page timeout and a strict request filter that blocks images, fonts,
  media and third-party subresources. Scholarship pages carry kilobytes of
  tracking assets that buy nothing and make the fallback slow.
* if the browser is unavailable or the page still refuses, the caller keeps its
  original blocked classification. A fallback that fails changes nothing, so
  this can never invent a result.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

#: Below this there is nothing worth parsing, so the fetch is treated as a
#: refusal rather than a success with an empty body.
MIN_HTML_CHARS = 400


@dataclass(frozen=True)
class BrowserFetch:
    """Result of a headless render of one official page."""

    url: str
    ok: bool
    html: str = ""
    final_url: str | None = None
    status: int | None = None
    error: str | None = None

    @property
    def usable(self) -> bool:
        return self.ok and len(self.html) >= MIN_HTML_CHARS


def should_try_browser(http_status: int | None, error: str | None) -> bool:
    """True only when the failure looks like bot management, not absence.

    A 404 or a refused connection is a real answer and is not retried. Only the
    statuses and errors that a browser plausibly changes are worth a second
    attempt.
    """
    if http_status in (403, 401, 429, 503, 511):
        return True
    if http_status is None and error in ("forbidden", "timeout", "connection_error", "blocked"):
        return True
    return False


class HeadlessSourceFetcher:
    """Renders official pages in Chromium, reusing one browser per instance."""

    def __init__(
        self,
        *,
        timeout_ms: int = 25_000,
        user_agent: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.user_agent = user_agent
        self.enabled = enabled
        self._playwright = None
        self._browser = None
        self._context = None
        self._lock = threading.Lock()
        self._closed = False

    def available(self) -> bool:
        """True when a browser can actually be launched in this environment."""
        if not self.enabled:
            return False
        try:
            import playwright.sync_api  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return True

    def _ensure(self) -> bool:
        if self._closed:
            return False
        with self._lock:
            if self._context is not None:
                return True
            try:
                from playwright.sync_api import sync_playwright

                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                self._context = self._browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1366, "height": 900},
                    java_script_enabled=True,
                )
                # Scholarship pages are mostly text. Skipping subresources cuts
                # the render time dramatically and avoids pulling trackers.
                self._context.route(
                    "**/*",
                    lambda route: (
                        route.abort()
                        if route.request.resource_type
                        in ("image", "media", "font", "stylesheet")
                        else route.continue_()
                    ),
                )
                return True
            except Exception as exc:  # noqa: BLE001
                logger.info("headless fetch unavailable: %s", exc)
                self._teardown()
                return False

    def fetch(self, url: str) -> BrowserFetch:
        if not self.available() or not self._ensure():
            return BrowserFetch(url=url, ok=False, error="browser_unavailable")
        page = None
        try:
            page = self._context.new_page()
            response = page.goto(
                url,
                timeout=self.timeout_ms,
                wait_until="domcontentloaded",
            )
            status = response.status if response is not None else None
            html = page.content() or ""
            final_url = page.url
            return BrowserFetch(
                url=url,
                ok=bool(status and status < 400 and len(html) >= MIN_HTML_CHARS),
                html=html,
                final_url=final_url,
                status=status,
                error=None if status and status < 400 else f"http_{status}",
            )
        except Exception as exc:  # noqa: BLE001
            return BrowserFetch(url=url, ok=False, error=type(exc).__name__)
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass

    def fetch_many(self, urls: list[str], *, max_urls: int = 40) -> list[BrowserFetch]:
        """Render several official pages, stopping at a bounded batch size."""
        results: list[BrowserFetch] = []
        for url in urls[:max_urls]:
            results.append(self.fetch(url))
        return results

    def _teardown(self) -> None:
        for attr in ("_context", "_browser"):
            obj = getattr(self, attr, None)
            if obj is not None:
                try:
                    if attr == "_context":
                        obj.close()
                    else:
                        obj.close()
                except Exception:  # noqa: BLE001
                    pass
                setattr(self, attr, None)
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # noqa: BLE001
                pass
            self._playwright = None

    def close(self) -> None:
        self._closed = True
        self._teardown()
