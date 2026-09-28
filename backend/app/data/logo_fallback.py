"""Fill blank image slots with the issuer's official logo, where one exists.

A scholarship card with no visual identity at all is a worse experience than a
card showing the official university or government mark, and the acceptance
rules treat an official issuer logo as a legitimate last-resort fallback.

This only ever installs an asset served by the record's OWN official host, and
only when that host is reachable: an unreachable host yields
OFFICIAL_URL_FOUND_FETCH_BLOCKED rather than a guess. The result is a real,
traceable, official asset - never a third-party or stock logo.
"""
from __future__ import annotations

import re
import sys
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.models import Scholarship
from app.services.image_evaluation_status import ImageEvaluationStatus

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

PERSIST = "--persist" in sys.argv
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 60

#: Only the issuer's own site. A logo hosted anywhere else is not the issuer's
#: identity and is not acceptable as a fallback.
_LOGO_RE = (
    re.compile(r'href="([^"]*(?:logo|brand|wordmark)[^"]*\.svg)"', re.I),
    re.compile(r'href="([^"]*(?:logo|brand|wordmark)[^"]*\.png)"', re.I),
    re.compile(r'src="([^"]*(?:logo|brand|wordmark)[^"]*\.(?:svg|png))"', re.I),
    re.compile(r'href="([^"]*/favicon[^"]*\.ico)"', re.I),
)


def _host(url: str | None) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().removeprefix("www.")


def _registrable(host: str) -> str:
    parts = host.split(".")
    return ".".join(parts[-3:]) if len(parts) > 2 else host


#: A logo that is genuinely a footer, header, sprite, theme or tracking asset is
#: chrome, not an identity mark. Installing one here would reintroduce exactly
#: the assets the image audit just purged, so the fallback refuses them.
_CHROME_LOGO = re.compile(
    r"(footer|header|sprite|theme|placeholder|spacer|1x1|pixel|"
    r"blank|spinner|loader|tracking|beacon|pixel|icon-|social)",
    re.IGNORECASE,
)


def _is_identity_logo(url: str) -> bool:
    return not _CHROME_LOGO.search(urlparse(url).path)


def _find_logo(html: str, base: str, host: str) -> str | None:
    for pattern in _LOGO_RE:
        for match in pattern.finditer(html):
            try:
                absolute = urljoin(base, match.group(1))
            except ValueError:
                continue
            if not absolute.lower().startswith("http"):
                continue
            if _host(absolute) != host:
                continue
            if not _is_identity_logo(absolute):
                continue
            return absolute
    return None


def _kind_for(host: str) -> str:
    if any(t in host for t in (".gov", "-gov.", "europa.eu", "un.org")):
        return "official_government"
    if any(t in host for t in (".edu", ".ac.", "university", "unibe", "hochschule")):
        return "official_university"
    return "official_logo"


def main() -> None:
    factory = get_session_factory()
    session = factory()
    try:
        rows = list(
            session.scalars(
                select(Scholarship).where(
                    Scholarship.verification_status != "quarantined"
                )
            )
        )
        blanks = [r for r in rows if not r.image_url and r.official_source_url]
        print(f"blank image slots: {len(blanks)}")
        filled = blocked = 0
        for row in blanks[:LIMIT]:
            official = _host(row.official_source_url)
            if not official:
                continue
            try:
                response = httpx.get(
                    row.official_source_url,
                    headers=UA,
                    timeout=15.0,
                    follow_redirects=True,
                )
            except Exception:  # noqa: BLE001
                blocked += 1
                continue
            if response.status_code != 200 or not response.text:
                blocked += 1
                continue
            final_host = _host(str(response.url))
            # Only the issuer's own site may supply the fallback.
            if _registrable(final_host) != _registrable(official):
                blocked += 1
                continue
            logo = _find_logo(response.text, str(response.url), final_host)
            if not logo:
                continue
            if PERSIST:
                row.image_url = logo
                row.image_source_url = str(response.url)
                row.image_source_type = "official_page_logo"
                row.image_kind = _kind_for(final_host)
                row.image_alt_text = f"{row.official_source or row.title} official logo"
                row.image_verified_at = datetime.now(timezone.utc)
                row.image_evaluation_status = ImageEvaluationStatus.VERIFIED
            filled += 1
            print(f"  id={row.id:<4} [{_kind_for(final_host)}] {logo[:74]}")
        if PERSIST:
            session.commit()
        print(
            f"\n{'installed' if PERSIST else 'would install'}: {filled}  "
            f"blocked/unreachable: {blocked}"
        )
    finally:
        session.close()


from datetime import datetime, timezone

if __name__ == "__main__":
    main()
