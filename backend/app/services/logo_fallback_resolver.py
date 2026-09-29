"""Three-tier fallback resolution for missing or blocked official logos.

About 170 valid scholarships are hidden from the public catalogue because no
image could be obtained. Three different situations are being conflated, and
each needs a different answer:

* **Tier 1 - root domain.** The programme page was blocked or had no logo, but
  the institution's own homepage usually carries the brand mark. Fetching the
  root is still *official* evidence, and the image still comes from the
  institution's own domain, so it passes the ordinary official checks.

* **Tier 2 - Wikimedia.** The domain blocks scrapers entirely. The
  institution's own logo artwork is frequently mirrored on Wikimedia Commons
  under a free licence. This is a genuine logo of the right institution, but
  it is **not** an official source: it is hosted by a third party. It is
  therefore recorded with a distinct ``wikimedia`` source type and can never be
  reported as an official-sourced image. Silently promoting a Commons file to
  "official" would be the single most damaging thing this module could do, so
  the distinction is carried in the type, not just in a comment.

* **Tier 3 - static override.** An audited mapping from a stable institution
  key to a known-good asset URL. Deterministic, free, and reviewable in a diff.

Every tier produces *candidates*. Selection still goes through the existing
``ImageValidator``, so tier 1 is judged by exactly the same rules as a logo
found on the programme page, and no tier can bypass a quality rule.

No tier fabricates evidence. A tier that finds nothing returns no candidate,
and the record keeps whatever terminal status it already had.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urljoin, urlparse

logger = logging.getLogger(__name__)

USER_AGENT = (
    "ScholarZoneBot/1.0 (scholarship catalogue; contact via repository)"
)
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# The Wikimedia API asks for a descriptive user agent; requests without one are
# rate-limited aggressively.
REQUEST_TIMEOUT = 20.0

OVERRIDE_PATH = Path(__file__).resolve().parents[2] / "config" / "official_logo_overrides.json"


class LogoTier(str, Enum):
    """Which fallback produced a candidate. Recorded, never guessed."""

    ROOT_DOMAIN = "root_domain"
    WIKIMEDIA = "wikimedia"
    STATIC_OVERRIDE = "static_override"


class LogoResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    NO_CANDIDATE = "no_candidate"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class LogoCandidate:
    """One proposed image, with the provenance the record must carry."""

    url: str
    tier: LogoTier
    page_url: str
    # True only for tiers whose bytes are served by the institution itself.
    # A Wikimedia file is the institution's artwork on a third-party host, so
    # this is False and the source type says so.
    official_host: bool
    alt_text: str | None = None
    note: str | None = None


@dataclass
class LogoResolution:
    status: LogoResolutionStatus
    tier: LogoTier | None = None
    candidates: list[LogoCandidate] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "tier": self.tier.value if self.tier else None,
            "candidates": len(self.candidates),
            "attempts": self.attempts,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def root_of(url: str | None) -> str | None:
    """The scheme+host of a URL, e.g. https://oxford.ac.uk."""
    if not url:
        return None
    try:
        parts = urlparse(url)
    except Exception:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    return f"{parts.scheme}://{parts.netloc}/"


def institution_key(scholarship) -> str:
    """A stable key for override lookup.

    The official source host is used rather than the title, because a title
    changes with an official rename while the domain does not. This is what
    makes the override file reviewable in a diff.
    """
    source = scholarship.official_source_url or ""
    host = urlparse(source).netloc.lower().removeprefix("www.") if source else ""
    if host:
        return host
    return (scholarship.country or "").strip().lower()


def _looks_like_logo(*values: str | None) -> bool:
    """Signals that an <img>/<link> is branding rather than a photo or icon."""
    text = " ".join(v for v in values if v).lower()
    if not text:
        return False
    if any(token in text for token in ("logo", "wordmark", "brandmark", "crest", "emblem")):
        return True
    if any(token in text for token in ("hero", "banner", "photo", "avatar", "profile", "sprite")):
        return False
    return False


_LOGO_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r"""(\w[\w-]*)\s*=\s*["']([^"']*)["']""")


def _attrs(tag: str) -> dict[str, str]:
    return {m.group(1).lower(): m.group(2) for m in _ATTR.finditer(tag)}


# ---------------------------------------------------------------------------
# The resolver
# ---------------------------------------------------------------------------


class LogoFallbackResolver:
    """Resolves logo candidates for a record through the three fallback tiers.

    ``fetch_text`` is injected so the whole thing is testable without a
    network, and so a caller can apply its own timeout, retry and circuit
    breaking rather than this module opening sockets directly.
    """

    def __init__(
        self,
        fetch_text: Callable[[str], str | None] | None = None,
        overrides: dict[str, dict[str, str]] | None = None,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._fetch_text = fetch_text or _default_fetch_text
        self._timeout = timeout
        self._overrides = overrides if overrides is not None else load_overrides()
        self.requests_made = 0

    # -- entry point --------------------------------------------------

    def resolve(self, scholarship) -> LogoResolution:
        """Try each tier in order and return the first that yields candidates."""
        resolution = LogoResolution(status=LogoResolutionStatus.NO_CANDIDATE)
        tiers = (
            (LogoTier.ROOT_DOMAIN, self.tier_root_domain),
            (LogoTier.STATIC_OVERRIDE, self.tier_static_override),
            (LogoTier.WIKIMEDIA, self.tier_wikimedia),
        )
        for tier, fn in tiers:
            try:
                candidates = fn(scholarship)
            except Exception as exc:  # noqa: BLE001
                # One broken tier must not stop the others; a provider being
                # down is an outcome, not a reason to abandon the record.
                logger.info("logo tier %s failed for id=%s: %s", tier.value, getattr(scholarship, "id", "?"), exc)
                resolution.attempts.append({"tier": tier.value, "error": str(exc)})
                continue
            resolution.attempts.append({"tier": tier.value, "candidates": len(candidates)})
            if candidates:
                resolution.status = LogoResolutionStatus.RESOLVED
                resolution.tier = tier
                resolution.candidates = candidates
                return resolution
        return resolution

    # -- tier 1: institution root domain ------------------------------

    def tier_root_domain(self, scholarship) -> list[LogoCandidate]:
        """Scrape the institution's own homepage for its brand mark.

        Still official evidence: the bytes are served by the institution's own
        domain, so candidates are marked ``official_host=True`` and go through
        exactly the same validator as a logo found on the programme page.
        """
        root = root_of(scholarship.official_source_url)
        if not root:
            return []
        host = urlparse(root).netloc.lower().removeprefix("www.")
        if _is_aggregator(host):
            # Portals like Study in Korea publish other institutions' logos on
            # their own domain. Those are not this scholarship's institution.
            return []

        html = self._fetch_text(root)
        if not html:
            return []

        found: list[LogoCandidate] = []
        seen: set[str] = set()

        for tag in _LOGO_TAG.findall(html)[:120]:
            attrs = _attrs(tag)
            src = attrs.get("src") or attrs.get("data-src") or ""
            if not src:
                continue
            absolute = urljoin(root, src)
            if not _is_image_url(absolute) or absolute in seen:
                continue
            if not _looks_like_logo(attrs.get("alt"), attrs.get("class"), attrs.get("id"), src):
                continue
            if not _same_host(absolute, root):
                continue
            seen.add(absolute)
            found.append(
                LogoCandidate(
                    url=absolute,
                    tier=LogoTier.ROOT_DOMAIN,
                    page_url=root,
                    official_host=True,
                    alt_text=attrs.get("alt"),
                    note="institution root domain brand mark",
                )
            )
            if len(found) >= 4:
                break
        return found

    # -- tier 2: wikimedia ---------------------------------------------

    def tier_wikimedia(self, scholarship) -> list[LogoCandidate]:
        """Look for the institution's logo on Wikimedia.

        Used when the official domain is unreachable. The image is the
        institution's own artwork, but it is **hosted by a third party**, so
        every candidate is marked ``official_host=False`` and the tier is
        recorded. It is never promoted to an official-sourced image.
        """
        title = (scholarship.title or "").strip()
        if not title:
            return []
        query = re.sub(r"\s+", " ", title)[:120]
        candidates: list[LogoCandidate] = []

        # The page image is the infobox photograph or logo, whichever the
        # article leads with, and is the cheapest single request to make.
        payload = self._api(WIKIPEDIA_API, {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "0",
            "gsrlimit": "1",
            "prop": "pageimages",
            "piprop": "original",
            "redirects": "1",
        })
        page = _first_page(payload)
        if page:
            original = (page.get("original") or {}).get("source")
            if original and _is_image_url(original):
                candidates.append(
                    LogoCandidate(
                        url=original,
                        tier=LogoTier.WIKIMEDIA,
                        page_url=f"https://en.wikipedia.org/wiki/{quote(str(page.get('title', '')).replace(' ', '_'))}",
                        official_host=False,
                        alt_text=str(page.get("title") or ""),
                        note="Wikimedia-hosted logo; third-party host, not an official source",
                    )
                )
        return candidates

    # -- tier 3: static override ---------------------------------------

    def tier_static_override(self, scholarship) -> list[LogoCandidate]:
        """An audited, deterministic mapping for institutions we know well."""
        entry = self._overrides.get(institution_key(scholarship))
        if not entry:
            return []
        url = (entry.get("url") or "").strip()
        if not url or not _is_image_url(url):
            logger.warning(
                "override for %s is not a usable image url", institution_key(scholarship)
            )
            return []
        return [
            LogoCandidate(
                url=url,
                tier=LogoTier.STATIC_OVERRIDE,
                page_url=entry.get("page_url") or root_of(scholarship.official_source_url) or "",
                official_host=bool(entry.get("official_host", False)),
                alt_text=entry.get("alt_text"),
                note="audited static override",
            )
        ]

    # -- transport ----------------------------------------------------

    def _api(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        url = endpoint + "?" + "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        self.requests_made += 1
        body = self._fetch_text(url)
        if not body:
            return {}
        try:
            return json.loads(body)
        except (ValueError, TypeError):
            return {}


def _first_page(payload: dict[str, Any]) -> dict[str, Any] | None:
    pages = (payload or {}).get("query", {}).get("pages", {})
    if not pages:
        return None
    # Dict ordering is not guaranteed, and a missing/invalid page comes back
    # with index "-1", so filter it out rather than trusting position 0.
    usable = [p for p in pages.values() if p and p.get("index") != "-1"]
    return usable[0] if usable else None


_AGGREGATOR_HOSTS = {
    "studyinkorea.go.kr", "studyinjapan.go.jp", "europa.eu",
    "erasmus-plus.ec.europa.eu", "commonwealthscholarships.org",
    "chevening.com", "daad.de", "fulbrightscholarships.org",
    "education.ec.europa.eu", "universityworldnews.com",
}


def _is_aggregator(host: str) -> bool:
    return any(host == a or host.endswith("." + a) for a in _AGGREGATOR_HOSTS)


def _same_host(candidate: str, page: str) -> bool:
    a = urlparse(candidate).netloc.lower().removeprefix("www.")
    b = urlparse(page).netloc.lower().removeprefix("www.")
    return bool(a) and a == b


def _is_image_url(url: str) -> bool:
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    return path.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"))


def _default_fetch_text(url: str) -> str | None:
    """Minimal text fetch. Injected in tests; never bypasses a block."""
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return None
    try:
        response = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code >= 400:
            return None
        return response.text
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Override file
# ---------------------------------------------------------------------------


def load_overrides(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load the audited override map. Absent or malformed file means no overrides.

    A broken config must degrade to "no overrides", never to a crash during a
    scheduled run, and never to something guessed.
    """
    target = path or OVERRIDE_PATH
    try:
        if not target.exists():
            return {}
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("could not read logo overrides from %s: %s", target, exc)
        return {}
    if not isinstance(data, dict):
        logger.warning("logo override file is not an object; ignoring")
        return {}
    # Keys beginning with "_" are documentation for the next person who edits
    # this file, not overrides. Loading them would let a comment block act as a
    # live mapping, which is exactly the kind of thing that goes unnoticed.
    return {
        str(k): v
        for k, v in data.items()
        if isinstance(v, dict) and not str(k).startswith("_")
    }
