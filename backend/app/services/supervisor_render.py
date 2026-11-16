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
barrier. A browser context is Playwright's incognito-equivalent unit: separate cookies
and storage per source, cheap to create. That matters for safety as well as
hygiene - it guarantees no state, cookie or session can carry from one
institution's directory into the next.

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
import inspect
import logging
import os
import sys
import time
from typing import Protocol

from .supervisor_source import (
    RenderBudget,
    RenderErrorKind,
    SourceObservation,
    SourceOutcome,
    detect_access_barrier,
)
from .outbound_proxy import OutboundProxy

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
        deadline_monotonic: float | None = None,
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


def _timeout_observation(url: str, budget: RenderBudget, started: float, scrolls: int = 0) -> SourceObservation:
    return SourceObservation(
        url=url,
        outcome=SourceOutcome.ERROR,
        error_kind=str(RenderErrorKind.PAGE_TIMEOUT),
        detail=f"Exceeded the {budget.total_seconds}s source budget.",
        elapsed_ms=int((time.monotonic() - started) * 1000),
        limits_used={"scrolls": scrolls} if scrolls else {},
    )


def _remaining_seconds(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


async def _await_with_deadline(coro, deadline: float):
    remaining = _remaining_seconds(deadline)
    if remaining <= 0:
        raise asyncio.TimeoutError()
    return await asyncio.wait_for(coro, timeout=remaining)


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
        self._outbound_proxy: OutboundProxy | None = None
        self._lock = asyncio.Lock()
        self._contexts_open = 0

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._outbound_proxy = OutboundProxy()
        proxy_server = await self._outbound_proxy.start()
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            proxy={"server": proxy_server, "bypass": "<-loopback>"},
            # Resource ceilings so a pathological page cannot consume the host.
            args=[
                "--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu",
                "--disable-background-networking", "--disable-dns-prefetch", "--disable-quic",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
            ],
        )

    async def close(self) -> None:
        # Capture references first, then clear instance variables to avoid
        # re-entrancy issues. Each resource is closed independently with its
        # own timeout so a stall in one doesn't block the others.
        browser = getattr(self, "_browser", None)
        playwright = getattr(self, "_playwright", None)
        proxy = getattr(self, "_outbound_proxy", None)
        self._browser = None
        self._playwright = None
        self._outbound_proxy = None

        # Each cleanup step gets its own short deadline. We attempt all three
        # regardless of individual failures, and log any abandoned cleanup.
        # We use asyncio.wait with ALL_COMPLETED to ensure all cleanup
        # attempts are made even if some are cancelled or fail.
        # We shield each cleanup from external cancellation.
        cleanup_timeout = 5.0  # seconds per resource

        # Create tasks for each cleanup operation, shielded from external cancellation
        tasks = []

        if browser is not None:
            async def _close_browser():
                try:
                    await asyncio.wait_for(asyncio.shield(browser.close()), timeout=cleanup_timeout)
                except asyncio.TimeoutError:
                    logger.warning("browser.close() timed out during cleanup; abandoned")
                except asyncio.CancelledError:
                    logger.warning("browser.close() cancelled during cleanup; abandoned")
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.debug("browser.close() failed during cleanup", exc_info=exc)
            tasks.append(asyncio.create_task(_close_browser()))

        if playwright is not None:
            async def _close_playwright():
                try:
                    await asyncio.wait_for(asyncio.shield(playwright.stop()), timeout=cleanup_timeout)
                except asyncio.TimeoutError:
                    logger.warning("playwright.stop() timed out during cleanup; abandoned")
                except asyncio.CancelledError:
                    logger.warning("playwright.stop() cancelled during cleanup; abandoned")
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.debug("playwright.stop() failed during cleanup", exc_info=exc)
            tasks.append(asyncio.create_task(_close_playwright()))

        if proxy is not None:
            async def _close_proxy():
                try:
                    result = proxy.close()
                    if inspect.isawaitable(result):
                        await asyncio.wait_for(asyncio.shield(result), timeout=cleanup_timeout)
                except asyncio.TimeoutError:
                    logger.warning("proxy.close() timed out during cleanup; abandoned")
                except asyncio.CancelledError:
                    logger.warning("proxy.close() cancelled during cleanup; abandoned")
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.debug("proxy.close() failed during cleanup", exc_info=exc)
            tasks.append(asyncio.create_task(_close_proxy()))

        # Wait for all cleanup tasks with a combined timeout.
        # We use asyncio.wait with ALL_COMPLETED to ensure all cleanup
        # attempts are made even if some are cancelled or fail.
        # We do not cancel other tasks if one fails.
        if tasks:
            total_cleanup_timeout = cleanup_timeout * len(tasks) + 2.0  # buffer
            done, pending = await asyncio.wait(
                tasks,
                timeout=total_cleanup_timeout,
                return_when=asyncio.ALL_COMPLETED
            )

            # Handle completed tasks
            for task in done:
                try:
                    task.result()
                except asyncio.CancelledError:
                    # Cancellation during cleanup - log but don't propagate yet
                    logger.warning("Cleanup task was cancelled")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Cleanup task failed", exc_info=exc)

            # Cancel any still-pending tasks (should be rare with proper timeouts)
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Pending cleanup task failed after cancel", exc_info=exc)

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
        deadline_monotonic: float | None = None,
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
        deadline = deadline_monotonic if deadline_monotonic is not None else (started + budget.total_seconds)
        context = None
        scrolls = 0
        try:
            if _remaining_seconds(deadline) <= 0:
                return _timeout_observation(url, budget, started, scrolls)

            async with self._lock:
                # Concurrency ceiling on live contexts, not just a convention.
                if self._contexts_open >= budget.max_concurrent_contexts:
                    return SourceObservation(
                        url=url,
                        outcome=SourceOutcome.ERROR,
                        error_kind=str(RenderErrorKind.BUDGET_EXHAUSTED),
                        detail="Too many concurrent browser contexts.",
                    )
                context = await _await_with_deadline(
                    self._browser.new_context(
                        # Anonymous by construction: no storage state, no user cookies.
                        storage_state=None,
                        service_workers="block",
                        java_script_enabled=True,
                    ),
                    deadline,
                )
                self._contexts_open += 1

            await _await_with_deadline(
                context.route(
                    "**/*",
                    lambda route: (
                        route.abort()
                        if route.request.resource_type in BLOCKED_RESOURCE_TYPES
                        else route.continue_()
                    ),
                ),
                deadline,
            )
            page = await _await_with_deadline(context.new_page(), deadline)

            nav_timeout_ms = budget.navigation_timeout_ms
            remaining_ms = int(_remaining_seconds(deadline) * 1000)
            if remaining_ms <= 0:
                return _timeout_observation(url, budget, started, scrolls)
            effective_timeout_ms = max(1, min(nav_timeout_ms, remaining_ms))
            page.set_default_timeout(effective_timeout_ms)
            page.set_default_navigation_timeout(effective_timeout_ms)

            response = await _await_with_deadline(
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=effective_timeout_ms,
                ),
                deadline,
            )

            # A deterministic condition first, then a capped settle. Fixed sleeps
            # are avoided because real SPAs vary by an order of magnitude.
            idle_timeout_ms = max(1, min(8_000, effective_timeout_ms, int(_remaining_seconds(deadline) * 1000) or 1))
            try:
                await _await_with_deadline(
                    page.wait_for_load_state("networkidle", timeout=idle_timeout_ms),
                    deadline,
                )
            except asyncio.TimeoutError:
                # Budget/deadline exhaustion is a hard timeout outcome.
                if _remaining_seconds(deadline) <= 0:
                    raise
                logger.debug("networkidle did not settle within budget cap for %s; continuing", url)
            except Exception:  # noqa: BLE001 - a page that never idles is normal
                logger.debug("networkidle did not settle for %s; continuing", url)

            # Bounded scroll for infinite-scroll directories. Each iteration is
            # counted, so termination does not depend on the site cooperating.
            if max_scroll_iterations:
                scrolls = await self._bounded_scroll(page, max_scroll_iterations, deadline=deadline)

            if _remaining_seconds(deadline) <= 0:
                return _timeout_observation(url, budget, started, scrolls)

            html = await _await_with_deadline(page.content(), deadline)
            if len(html) > budget.max_content_bytes:
                html = html[: budget.max_content_bytes]
                logger.info("Truncated rendered content for %s at %s bytes", url, budget.max_content_bytes)

            elapsed_ms = int((time.monotonic() - started) * 1000)
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

            if _remaining_seconds(deadline) <= 0:
                return _timeout_observation(url, budget, started, scrolls)

            return SourceObservation(
                url=url,
                outcome=SourceOutcome.SUCCESS,
                html=html,
                discovery_path="browser_render",
                elapsed_ms=elapsed_ms,
                limits_used={"scrolls": scrolls},
            )

        except asyncio.TimeoutError:
            return _timeout_observation(url, budget, started, scrolls)
        except Exception as exc:  # noqa: BLE001 - every failure must be classified
            if _remaining_seconds(deadline) <= 0:
                return _timeout_observation(url, budget, started, scrolls)
            return self._classify_exception(url, exc, started)
        finally:
            if context is not None:
                async with self._lock:
                    self._contexts_open = max(0, self._contexts_open - 1)
                try:
                    await context.close()
                except Exception:  # noqa: BLE001 - closing must never mask a result
                    pass

    async def _bounded_scroll(self, page, max_iterations: int, *, deadline: float | None = None) -> int:
        """Scroll in fixed increments, stopping as soon as nothing new appears.

        Counts its own iterations and stops on the first one that adds no profile
        links, so a site that never stops loading still terminates.
        """
        if deadline is not None and _remaining_seconds(deadline) <= 0:
            raise asyncio.TimeoutError()

        previous = await (_await_with_deadline(page.eval_on_selector_all("a[href]", "els => els.length"), deadline) if deadline is not None else page.eval_on_selector_all("a[href]", "els => els.length"))
        for iteration in range(max_iterations):
            if deadline is not None and _remaining_seconds(deadline) <= 0:
                raise asyncio.TimeoutError()
            await (_await_with_deadline(page.evaluate("window.scrollBy(0, window.innerHeight * 2)"), deadline) if deadline is not None else page.evaluate("window.scrollBy(0, window.innerHeight * 2)"))

            if deadline is not None:
                wait_ms = max(1, min(250, int(_remaining_seconds(deadline) * 1000)))
                await _await_with_deadline(page.wait_for_timeout(wait_ms), deadline)
                network_idle_timeout = max(1, min(3_000, int(_remaining_seconds(deadline) * 1000)))
                try:
                    await _await_with_deadline(page.wait_for_load_state("networkidle", timeout=network_idle_timeout), deadline)
                except asyncio.TimeoutError:
                    if _remaining_seconds(deadline) <= 0:
                        raise
                except Exception:  # noqa: BLE001
                    pass
                current = await _await_with_deadline(page.eval_on_selector_all("a[href]", "els => els.length"), deadline)
            else:
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
        deadline_monotonic: float | None = None,
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
    def run_in_fresh_loop(awaitable):
        # Playwright starts its driver with asyncio subprocess APIs. Windows'
        # selector loop does not implement subprocess transports, so its loop
        # must be a Proactor even if the test harness changed global policy.
        loop_factory = asyncio.ProactorEventLoop if sys.platform == "win32" else None
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            return runner.run(awaitable)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return run_in_fresh_loop(coroutine)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run_in_fresh_loop, coroutine).result()


async def _call_render_with_optional_deadline(
    driver: RenderDriver,
    url: str,
    *,
    budget: RenderBudget,
    seed_host: str,
    max_scroll_iterations: int,
    deadline_monotonic: float | None,
) -> SourceObservation:
    try:
        signature = inspect.signature(driver.render)
        if "deadline_monotonic" in signature.parameters:
            return await driver.render(
                url,
                budget=budget,
                seed_host=seed_host,
                max_scroll_iterations=max_scroll_iterations,
                deadline_monotonic=deadline_monotonic,
            )
    except (TypeError, ValueError):
        pass
    return await driver.render(
        url,
        budget=budget,
        seed_host=seed_host,
        max_scroll_iterations=max_scroll_iterations,
    )


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
            started = time.monotonic()
            deadline = started + budget.total_seconds
            primary: SourceObservation | None = None
            try:
                if isinstance(active, PlaywrightRenderDriver):
                    try:
                        await _await_with_deadline(active.start(), deadline)
                    except asyncio.TimeoutError:
                        primary = _timeout_observation(url, budget, started)
                    except Exception as exc:  # noqa: BLE001 - startup failures are inconclusive
                        logger.exception("Browser startup failed for %s", url)
                        primary = SourceObservation(
                            url=url,
                            outcome=SourceOutcome.ERROR,
                            error_kind=str(RenderErrorKind.BROWSER_UNAVAILABLE),
                            detail=type(exc).__name__,
                            elapsed_ms=int((time.monotonic() - started) * 1000),
                        )

                if primary is None:
                    try:
                        primary = await _call_render_with_optional_deadline(
                            active,
                            url,
                            budget=budget,
                            seed_host=seed_host,
                            max_scroll_iterations=max_scroll_iterations,
                            deadline_monotonic=deadline,
                        )
                    except asyncio.TimeoutError:
                        primary = _timeout_observation(url, budget, started)
                    except Exception as exc:  # noqa: BLE001 - startup failures are inconclusive
                        if isinstance(active, PlaywrightRenderDriver):
                            logger.exception("Browser startup failed for %s", url)
                            primary = SourceObservation(
                                url=url,
                                outcome=SourceOutcome.ERROR,
                                error_kind=str(RenderErrorKind.BROWSER_UNAVAILABLE),
                                detail=type(exc).__name__,
                                elapsed_ms=int((time.monotonic() - started) * 1000),
                            )
                        else:
                            raise

                if _remaining_seconds(deadline) <= 0 and primary.outcome != SourceOutcome.ERROR:
                    primary = _timeout_observation(url, budget, started, primary.limits_used.get("scrolls", 0))
                return primary
            finally:
                if isinstance(active, PlaywrightRenderDriver):
                    # Close the driver. The close() method now handles its own
                    # per-resource timeouts and is shielded from external cancellation.
                    # We don't wrap it in an outer timeout to avoid cancelling the
                    # individual resource cleanup steps.
                    try:
                        await active.close()
                    except asyncio.TimeoutError:
                        # This should not happen with the new close() implementation,
                        # but log it just in case.
                        logger.warning("Owned-driver cleanup timed out for %s", url)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Owned-driver cleanup failed for %s", url, exc_info=exc)

        return _run_coroutine(_session())

    async def _shared() -> SourceObservation:
        started = time.monotonic()
        deadline = started + budget.total_seconds
        try:
            remaining = _remaining_seconds(deadline)
            if remaining <= 0:
                return _timeout_observation(url, budget, started)
            observation = await asyncio.wait_for(
                _call_render_with_optional_deadline(
                    active,
                    url,
                    budget=budget,
                    seed_host=seed_host,
                    max_scroll_iterations=max_scroll_iterations,
                    deadline_monotonic=deadline,
                ),
                timeout=remaining,
            )
            if _remaining_seconds(deadline) <= 0 and observation.outcome != SourceOutcome.ERROR:
                return _timeout_observation(
                    url, budget, started, observation.limits_used.get("scrolls", 0)
                )
            return observation
        except asyncio.TimeoutError:
            return _timeout_observation(url, budget, started)

    return _run_coroutine(_shared())


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