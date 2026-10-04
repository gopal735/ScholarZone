"""Bounded browser rendering for JavaScript-rendered institutional directories.

This is the fallback tier. It runs only when the static tier read a page and
found a client-side shell, and it is the only place in the codebase that executes
JavaScript.

Three properties define it.

**It is bounded, structurally.** A :class:`~app.services.supervisor_source.RenderBudget`
has no unbounded dimension - not pages, not scrolls, not pagination, not
candidates, not content size, not wall clock. Every loop in this module is driven
by a counter from that budget, so termination is a property of the code rather
than a hope about the network.

**It cannot defeat an access control.** A login wall or an anti-bot challenge is
*detected* and reported as ``source_blocked``. There is no credential handling, no
CAPTCHA solving, no stealth patching, no proxy rotation, and no retry against a
barrier. A browser context is created without a storage state and without any
cookie the user holds, so a request it makes is anonymous by construction.

**It is optional and off by default.** If the driver is not installed, if the
configuration flag is off, or if the browser cannot start, the answer is
``SOURCE_REQUIRES_RENDERING`` - never a negative, and never an exception that
aborts a batch.

Waiting strategy follows what the research says works: prefer a deterministic
condition over a fixed sleep, use ``networkidle`` only with a hard cap because
pages with polling never settle, and block images, fonts and media because they
cost time and memory without carrying evidence.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Protocol

from .supervisor_source import (
    RenderBudget,
    RenderErrorKind,
    SourceObservation,
    SourceOutcome,
    detect_access_barrier,
)

logger = logging.getLogger(__name__)

#: Configuration flag. Off unless an operator turns it on, so the normal
#: maintenance path never launches a browser.
RENDER_ENABLED_ENV = "SCHOLARZONE_SUPERVISOR_RENDER_ENABLED"

#: Asset types blocked during a render. They are not evidence and they are the
#: bulk of the transfer, which is why a directory that blocks them renders much
#: faster and within a far smaller memory ceiling.
BLOCKED_RESOURCE_TYPES = {"image", "font", "media"}


def rendering_enabled() -> bool:
    """Whether an operator has opted in to browser rendering."""
    return os.environ.get(RENDER_ENABLED_ENV, "").strip().lower() in ("1", "true", "yes", "on")


class RenderDriver(Protocol):
    """What the pipeline needs from a browser.

    A protocol rather than a concrete type so the driver can be substituted in
    tests and so a future driver can be added without touching the pipeline. The
    pipeline never learns which implementation rendered a page.
    """

    async def render(
        self,
        url: str,
        *,
        budget: RenderBudget,
        seed_host: str,
        max_scroll_iterations: int = 0,
    ) -> SourceObservation:
        ...


def playwright_available() -> bool:
    """Whether a usable browser driver is importable.

    Imported lazily and defensively: the whole point is that this feature can run
    in an environment without it and degrade to an inconclusive state.
    """
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except Exception:  # noqa: BLE001 - any import problem means "not available"
        return False
    return True


def _map_http_status(status: int | None) -> str | None:
    if status is None:
        return None
    if status == 403:
        return str(RenderErrorKind.HTTP_403)
    if status == 404:
        return str(RenderErrorKind.HTTP_404)
    if status == 429:
        return str(RenderErrorKind.HTTP_429)
    if 500 <= status < 600:
        return str(RenderErrorKind.HTTP_5XX)
    if status >= 400:
        return str(RenderErrorKind.HTTP_ERROR)
    return None


class PlaywrightRenderDriver:
    """One browser, one isolated context per source, hard-bounded.

    A browser context is Playwright's incognito-equivalent unit: separate cookies
    and storage per source, cheap to create. That matters for safety as well as
    hygiene - it guarantees no state, cookie or session can carry from one
    institution's directory into the next.
    """

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()
        self._contexts_open = 0

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            # Resource ceilings so a pathological page cannot consume the host.
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
        )

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self) -> "PlaywrightRenderDriver":
        await self.start()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def render(
        self,
        url: str,
        *,
        budget: RenderBudget,
        seed_host: str,
        max_scroll_iterations: int = 0,
    ) -> SourceObservation:
        """Render one URL within ``budget`` and return what was observed."""
        if not rendering_enabled():
            return SourceObservation(
                url=url,
                outcome=SourceOutcome.SOURCE_REQUIRES_RENDERING,
                error_kind=str(RenderErrorKind.DISABLED_BY_CONFIG),
                detail="Browser rendering is not enabled; the source needs rendering.",
            )
        if not playwright_available():
            return SourceObservation(
                url=url,
                outcome=SourceOutcome.SOURCE_REQUIRES_RENDERING,
                error_kind=str(RenderErrorKind.BROWSER_UNAVAILABLE),
                detail="No browser driver is installed.",
            )
        if self._browser is None:
            return SourceObservation(
                url=url,
                outcome=SourceOutcome.ERROR,
                error_kind=str(RenderErrorKind.BROWSER_UNAVAILABLE),
                detail="Browser was not started.",
            )

        started = time.monotonic()
        context = None
        try:
            async with self._lock:
                # Concurrency ceiling on live contexts, not just a convention.
                if self._contexts_open >= budget.max_concurrent_contexts:
                    return SourceObservation(
                        url=url,
                        outcome=SourceOutcome.ERROR,
                        error_kind=str(RenderErrorKind.BUDGET_EXHAUSTED),
                        detail="Too many concurrent browser contexts.",
                    )
                context = await self._browser.new_context(
                    # Anonymous by construction: no storage state, no user cookies.
                    storage_state=None,
                    service_workers="block",
                )
                self._contexts_open += 1

            await context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in BLOCKED_RESOURCE_TYPES
                    else route.continue_()
                ),
            )
            page = await context.new_page()
            page.set_default_timeout(budget.navigation_timeout_ms)
            page.set_default_navigation_timeout(budget.navigation_timeout_ms)

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=budget.navigation_timeout_ms,
            )

            # A deterministic condition first, then a capped settle. Fixed sleeps
            # are avoided because real SPAs vary by an order of magnitude.
            try:
                await page.wait_for_load_state(
                    "networkidle", timeout=min(8_000, budget.navigation_timeout_ms)
                )
            except Exception:  # noqa: BLE001 - a page that never idles is normal
                logger.debug("networkidle did not settle for %s; continuing", url)

            # Bounded scroll for infinite-scroll directories. Each iteration is
            # counted, so termination does not depend on the site cooperating.
            scrolls = 0
            if max_scroll_iterations:
                scrolls = await self._bounded_scroll(page, max_scroll_iterations)

            html = await page.content()
            if len(html) > budget.max_content_bytes:
                html = html[: budget.max_content_bytes]
                logger.info("Truncated rendered content for %s at %s bytes", url, budget.max_content_bytes)

            elapsed_ms = int((time.monotonic() - started) * 1000)
            elapsed_seconds = time.monotonic() - started
            status = response.status if response is not None else None

            barrier = detect_access_barrier(html)
            if barrier:
                kind, marker = barrier
                return SourceObservation(
                    url=url,
                    outcome=SourceOutcome.SOURCE_BLOCKED,
                    error_kind=str(
                        RenderErrorKind.LOGIN_REQUIRED
                        if kind == "login_required"
                        else RenderErrorKind.ANTI_BOT_CHALLENGE
                    ),
                    detail=f"Access barrier ({marker}); not attempted.",
                    elapsed_ms=elapsed_ms,
                    limits_used={"scrolls": scrolls},
                )

            http_error = _map_http_status(status)
            if http_error:
                return SourceObservation(
                    url=url,
                    outcome=SourceOutcome.SOURCE_BLOCKED,
                    error_kind=http_error,
                    detail=f"HTTP {status}",
                    elapsed_ms=elapsed_ms,
                )

            if elapsed_seconds > budget.total_seconds:
                return SourceObservation(
                    url=url,
                    outcome=SourceOutcome.ERROR,
                    error_kind=str(RenderErrorKind.PAGE_TIMEOUT),
                    detail=f"Exceeded the {budget.total_seconds}s source budget.",
                    elapsed_ms=elapsed_ms,
                )

            return SourceObservation(
                url=url,
                outcome=SourceOutcome.SUCCESS,
                html=html,
                discovery_path="browser_render",
                elapsed_ms=elapsed_ms,
                limits_used={"scrolls": scrolls},
            )

        except Exception as exc:  # noqa: BLE001 - every failure must be classified
            return self._classify_exception(url, exc, started)
        finally:
            if context is not None:
                async with self._lock:
                    self._contexts_open = max(0, self._contexts_open - 1)
                try:
                    await context.close()
                except Exception:  # noqa: BLE001 - closing must never mask a result
                    pass

    async def _bounded_scroll(self, page, max_iterations: int) -> int:
        """Scroll in fixed increments, stopping as soon as nothing new appears.

        Counts its own iterations and stops on the first one that adds no profile
        links, so a site that never stops loading still terminates.
        """
        previous = await page.eval_on_selector_all("a[href]", "els => els.length")
        for iteration in range(max_iterations):
            await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            await page.wait_for_timeout(250)
            try:
                await page.wait_for_load_state("networkidle", timeout=3_000)
            except Exception:  # noqa: BLE001
                pass
            current = await page.eval_on_selector_all("a[href]", "els => els.length")
            if current <= previous:
                return iteration + 1
            previous = current
        return max_iterations

    def _classify_exception(self, url: str, exc: Exception, started: float) -> SourceObservation:
        """Map a browser failure onto the explicit taxonomy.

        Nothing here can produce a negative: every branch is ``ERROR`` or
        ``SOURCE_BLOCKED``, so a crash cannot be read as "no professors".
        """
        elapsed_ms = int((time.monotonic() - started) * 1000)
        name = type(exc).__name__
        text = str(exc).lower()

        if "timeout" in name.lower() or "timeout" in text:
            kind = RenderErrorKind.PAGE_TIMEOUT
        elif "net::err_name_not_resolved" in text or "getaddrinfo" in text:
            kind = RenderErrorKind.DNS_FAILURE
        elif "net::err_cert" in text or "ssl" in text:
            kind = RenderErrorKind.TLS_FAILURE
        elif "crash" in text or "target closed" in text or "browser has been closed" in text:
            kind = RenderErrorKind.BROWSER_CRASH
        else:
            kind = RenderErrorKind.UNKNOWN

        logger.info("Render failed for %s: %s (%s)", url, name, kind)
        return SourceObservation(
            url=url,
            outcome=SourceOutcome.ERROR,
            error_kind=str(kind),
            detail=f"{name}",
            elapsed_ms=elapsed_ms,
        )


class NullRenderDriver:
    """The driver used when rendering is unavailable or disabled.

    It exists so the pipeline can call the same interface unconditionally and get
    an honest inconclusive answer, rather than branching on a flag at every call
    site and risking one site being written without it.
    """

    def __init__(self, reason: str = "Rendering unavailable") -> None:
        self._reason = reason

    async def render(
        self,
        url: str,
        *,
        budget: RenderBudget,
        seed_host: str,
        max_scroll_iterations: int = 0,
    ) -> SourceObservation:
        return SourceObservation(
            url=url,
            outcome=SourceOutcome.SOURCE_REQUIRES_RENDERING,
            error_kind=str(RenderErrorKind.DISABLED_BY_CONFIG),
            detail=self._reason,
        )


def build_driver() -> RenderDriver:
    """Return the driver the pipeline should use, or an honest null driver."""
    if not rendering_enabled():
        return NullRenderDriver("Browser rendering is disabled by configuration.")
    if not playwright_available():
        return NullRenderDriver("No browser driver is installed.")
    return PlaywrightRenderDriver()


def _run_coroutine(coroutine):
    """Run a coroutine from synchronous code.

    The browser driver is async because Playwright's driver is, while the
    discovery pipeline is synchronous like everything else in this repository.
    When a loop is already running - a test harness, or an async caller - the
    coroutine is handed to a short-lived thread with its own loop rather than
    raising, so a render degrades into an inconclusive outcome instead of an
    exception.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def render_blocking(
    url: str,
    *,
    budget: RenderBudget,
    seed_host: str,
    max_scroll_iterations: int = 0,
    driver: RenderDriver | None = None,
) -> SourceObservation:
    """Render one URL and return the observation, from synchronous code.

    A driver supplied by the caller is used as-is; otherwise one is created and
    closed around this single page. That keeps the common case - one shell, one
    render - free of shared global browser state, while a batch that renders many
    sources can pass a long-lived driver in.
    """
    owns_driver = driver is None
    active = driver or build_driver()

    if owns_driver:
        # Start, render and close inside a *single* event loop. Playwright objects
        # are bound to the loop that created them, so one asyncio.run() per step
        # would hand the second call a browser attached to a dead loop - which
        # surfaces as a baffling AttributeError rather than a lifecycle error.
        async def _session() -> SourceObservation:
            if isinstance(active, PlaywrightRenderDriver):
                await active.start()
            try:
                return await active.render(
                    url,
                    budget=budget,
                    seed_host=seed_host,
                    max_scroll_iterations=max_scroll_iterations,
                )
            finally:
                if isinstance(active, PlaywrightRenderDriver):
                    await active.close()

        return _run_coroutine(_session())

    return _run_coroutine(
        active.render(
            url,
            budget=budget,
            seed_host=seed_host,
            max_scroll_iterations=max_scroll_iterations,
        )
    )


__all__ = [
    "BLOCKED_RESOURCE_TYPES",
    "NullRenderDriver",
    "PlaywrightRenderDriver",
    "RENDER_ENABLED_ENV",
    "RenderDriver",
    "build_driver",
    "playwright_available",
    "render_blocking",
    "rendering_enabled",
]