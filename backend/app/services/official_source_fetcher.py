"""Isolated HTTP fetcher for official scholarship sources."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict


class OfficialSourceFetchResult(BaseModel):
    """Structured outcome of fetching an official scholarship source."""

    model_config = ConfigDict(frozen=True)

    success: bool
    status_code: int | None = None
    final_url: str | None = None
    content: str | None = None
    content_type: str | None = None
    error_type: str | None = None
    error_reason: str | None = None


DEFAULT_TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=10.0,
    write=5.0,
    pool=5.0,
)

DEFAULT_HEADERS = {
    "User-Agent": "ScholarZone/1.0 (scholarship-verification-bot; +https://scholarzone.example.com)",
}


def _is_html_content(content_type: str) -> bool:
    if not content_type:
        return True
    normalized = content_type.lower()
    return "text/html" in normalized or "application/xhtml+xml" in normalized


def fetch_official_source(url: str) -> OfficialSourceFetchResult:
    """Fetch an official scholarship source URL and return a structured result.

    Never raises. All failures are captured in the returned result.
    """
    if not url or not url.strip():
        return OfficialSourceFetchResult(
            success=False,
            error_type="invalid_url",
            error_reason="URL is empty or missing",
        )

    try:
        with httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        ) as client:
            response = client.get(url)

            content_type = response.headers.get("content-type", "")
            final_url = str(response.url) if response.url else url

            try:
                content = response.text
            except Exception:
                content = None

            if response.status_code == httpx.codes.OK:
                if not _is_html_content(content_type):
                    return OfficialSourceFetchResult(
                        success=False,
                        status_code=response.status_code,
                        final_url=final_url,
                        content=content,
                        content_type=content_type,
                        error_type="invalid_content_type",
                        error_reason=f"Expected HTML content, got {content_type or 'unknown'}",
                    )
                return OfficialSourceFetchResult(
                    success=True,
                    status_code=response.status_code,
                    final_url=final_url,
                    content=content,
                    content_type=content_type,
                )

            if response.status_code == httpx.codes.NOT_FOUND:
                return OfficialSourceFetchResult(
                    success=False,
                    status_code=response.status_code,
                    final_url=final_url,
                    error_type="not_found",
                    error_reason="Official source returned 404 Not Found",
                )

            if response.status_code == httpx.codes.FORBIDDEN:
                return OfficialSourceFetchResult(
                    success=False,
                    status_code=response.status_code,
                    final_url=final_url,
                    error_type="forbidden",
                    error_reason="Access to official source was denied (403 Forbidden)",
                )

            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                return OfficialSourceFetchResult(
                    success=False,
                    status_code=response.status_code,
                    final_url=final_url,
                    error_type="rate_limited",
                    error_reason="Official source rate-limited the request (429 Too Many Requests)",
                )

            if response.status_code >= 500:
                return OfficialSourceFetchResult(
                    success=False,
                    status_code=response.status_code,
                    final_url=final_url,
                    error_type="server_error",
                    error_reason=f"Official source server error ({response.status_code})",
                )

            return OfficialSourceFetchResult(
                success=False,
                status_code=response.status_code,
                final_url=final_url,
                error_type="client_error",
                error_reason=f"Official source returned error ({response.status_code})",
            )

    except httpx.TimeoutException:
        return OfficialSourceFetchResult(
            success=False,
            error_type="timeout",
            error_reason="Request to official source timed out",
        )
    except httpx.RequestError:
        return OfficialSourceFetchResult(
            success=False,
            error_type="connection_error",
            error_reason="Failed to connect to official source",
        )
    except Exception as exc:
        return OfficialSourceFetchResult(
            success=False,
            error_type="unexpected_error",
            error_reason=f"Unexpected error during fetch: {exc}",
        )
