"""Official page discovery for Phase 9.

Finds trustworthy official pages (announcement/news/press/scholarship pages)
for a scholarship record without weakening the existing Phase 8 discovery
pipeline or the SourceResolverService.WEAK_PAGE_PENALTIES rules.

The service is read-only by default: it discovers and scores pages but does
not mutate the database. The orchestrator decides whether and how to persist.
"""

from __future__ import annotations



from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from .discovery_config import _extract_domain
from .image_discovery import ImageDiscoveryService, PageFetchResult

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_PAGES_PER_SCHOLARSHIP = 25
DEFAULT_MAX_REQUESTS_PER_SCHOLARSHIP = 40
DEFAULT_MAX_CRAWL_DEPTH = 2
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_REQUEST_INTERVAL_SECONDS = 0.25

# Common announcement / news / press path fragments (lowercased, matched as
# substrings of the page path). These are intentionally broad so we can find
# trustworthy pages; scoring happens later via relevance.
ANNOUNCEMENT_PATH_PATTERNS = (
    "announcement",
    "news",
    "press",
    "media",
    "story",
    "article",
    "blog",
    "update",
    "alert",
    "notice",
    "call",
    "open",
    "apply",
    "deadline",
    "result",
    "outcome",
    "event",
    "activity",
    "research",
    "publication",
    "scholarship",
    "funding",
    "grant",
    "opportunity",
    "program",
    "fellowship",
    "award",
    "prize",
    "competition",
    "information",
    "info",
    "detail",
    "page",
    "about",
    "contact",
)

# Path fragments that indicate a page is NOT a trustworthy official page.
NON_OFFICIAL_PATH_PATTERNS = (
    "/login",
    "/signin",
    "/signup",
    "/register/account",
    "/cart",
    "/checkout",
    "/payment",
    "/billing",
    "/account",
    "/profile",
    "/settings",
    "/admin",
    "/wp-admin",
    "/cdn/",
    "/assets/",
    "/static/",
    "/media/",
    "/uploads/",
    "/download",
    "/download/",
    "/file/",
    "/files/",
)

# Sitemap filenames commonly used by official sites.
SITEMAP_FILENAMES = (
    "sitemap.xml",
    "sitemap_index.xml",
    "sitemap-news.xml",
    "sitemap.php",
    "sitemap.txt",
    "sitemap.html",
    "sitemap-staff.xml",
)

# Common sub-paths probed on a root domain when no sitemap is available.
COMMON_OFFICIAL_PATHS = (
    "/scholarships",
    "/scholarship",
    "/funding",
    "/grants",
    "/grants-and-funding",
    "/opportunities",
    "/programs",
    "/programmes",
    "/fellowships",
    "/awards",
    "/news",
    "/announcements",
    "/press",
    "/media",
    "/about",
    "/contact",
    "/apply",
    "/application",
    "/for-students",
    "/students",
    "/study",
    "/international",
)



"""Chunk 2: enums and dataclasses for official page discovery."""


from dataclasses import dataclass, field
from enum import Enum


class PageKind(str, Enum):
    """Classification of an official page discovered for a scholarship."""

    SCHOLARSHIP_PAGE = "scholarship_page"
    ANNOUNCEMENT = "announcement"
    NEWS = "news"
    PRESS = "press"
    APPLICATION_PAGE = "application_page"
    ROOT_DOMAIN = "root_domain"
    SITEMAP = "sitemap"
    UNKNOWN = "unknown"


class DiscoveryConfidence(str, Enum):
    """Confidence tier for a discovered official page."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class OfficialPageCandidate:
    """A single discovered official page for a scholarship."""

    url: str
    normalized_url: str
    page_kind: PageKind
    source_domain: str
    is_official_domain: bool
    trust_score: int
    relevance_score: float
    confidence: DiscoveryConfidence
    discovery_method: str
    title: str | None = None
    snippet: str | None = None
    crawl_depth: int = 0
    http_status: int | None = None
    fetch_error: str | None = None
    is_trustworthy: bool = False
    provenance: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)

    def is_trustworthy_page(self) -> bool:
        return self.is_trustworthy


@dataclass
class DiscoveryOutcome:
    """Aggregate result of discovering official pages for one scholarship."""

    scholarship_id: int | None
    scholarship_title: str
    official_source_url: str | None
    official_domain: str | None
    is_official_domain: bool
    candidates: list[OfficialPageCandidate] = field(default_factory=list)
    trusted_candidates: list[OfficialPageCandidate] = field(default_factory=list)
    requests_made: int = 0
    pages_fetched: int = 0
    sitemaps_found: list[str] = field(default_factory=list)
    timed_out: bool = False
    bounded: bool = False
    error: str | None = None

    def best_candidate(self) -> OfficialPageCandidate | None:
        if self.trusted_candidates:
            return max(self.trusted_candidates, key=lambda c: (c.relevance_score, c.trust_score))
        if self.candidates:
            return max(self.candidates, key=lambda c: (c.relevance_score, c.trust_score))
        return None


@dataclass(frozen=True)
class DomainResolution:
    """Result of resolving a scholarship to an official domain."""

    official_domain: str | None
    is_official_domain: bool
    trust_score: int
    source_type: str | None
    resolution_method: str
    confidence: DiscoveryConfidence
    evidence: list[str] = field(default_factory=list)



"""Chunk 3: URL canonicalization and domain utilities."""


import re
from urllib.parse import parse_qsl, urlparse, urlunparse

from .discovery_config import _extract_domain
from .scholarship_image_verifier import is_official_domain



def canonicalize_url(url: str) -> str:
    """Normalize a URL for dedupe/comparison.

    - lowercases scheme and host
    - strips default ports
    - removes fragment
    - sorts query parameters
    - collapses trailing slashes (root keeps a single slash)
    """
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    if ":" in netloc:
        host, _, port = netloc.rpartition(":")
        if (scheme == "https" and port == "443") or (scheme == "http" and port == "80"):
            netloc = host
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if path == "":
        path = "/"
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query_pairs.sort()
    query = "&".join(f"{k}={v}" for k, v in query_pairs)
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def same_canonical_url(left: str, right: str) -> bool:
    return canonicalize_url(left) == canonicalize_url(right)


def is_root_url(url: str) -> bool:
    parsed = urlparse(url)
    return not parsed.path or parsed.path == "/"


def is_same_domain(url: str, domain: str) -> bool:
    host = _extract_domain(url)
    if not host or not domain:
        return False
    if host == domain:
        return True
    if host.endswith("." + domain) or domain.endswith("." + host):
        return True
    return False


def join_url(base: str, relative: str) -> str | None:
    if not relative:
        return None
    try:
        joined = urljoin(base, relative)
    except Exception:
        return None
    if not joined:
        return None
    parsed = urlparse(joined)
    if parsed.scheme not in ("http", "https"):
        return None
    return canonicalize_url(joined)


def path_segments(url: str) -> list[str]:
    parsed = urlparse(url)
    return [seg for seg in parsed.path.split("/") if seg]


def path_lower(url: str) -> str:
    return urlparse(url).path.lower()


def looks_like_page_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    path = parsed.path.lower()
    if not path or path == "/":
        return True
    asset_ext = (
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico",
        ".tif", ".tiff", ".pdf", ".zip", ".tar", ".gz", ".mp4", ".webm",
        ".mp3", ".wav", ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    )
    if path.endswith(asset_ext):
        return False
    return True


def is_non_trustworthy_path(url: str) -> bool:
    path = path_lower(url)
    for pat in NON_OFFICIAL_PATH_PATTERNS:
        if pat in path:
            return True
    return False


_TITLE_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return _TITLE_TOKEN_RE.findall(text.lower())


def token_overlap_score(title_tokens: list[str], text: str | None) -> float:
    if not title_tokens or not text:
        return 0.0
    text_tokens = set(tokenize(text))
    if not text_tokens:
        return 0.0
    matched = sum(1 for t in title_tokens if t in text_tokens)
    return matched / len(title_tokens)



"""Chunk 4: Domain resolution and page relevance scoring."""


from dataclasses import dataclass
from typing import TYPE_CHECKING

from .discovery_config import (
    ApprovedSourceData,
    StaticSourceRegistry,
    _DEFAULT_SOURCES,
    _extract_domain,
)
from .scholarship_image_verifier import is_official_domain


def _is_non_official_tld(domain: str) -> bool:
    """Return True for TLDs that are NOT inherently official."""
    non_official_tlds = (".org", ".com", ".net", ".biz", ".info", ".co", ".io", ".me")
    # Check the last two labels (TLD + SLD) for known non-official combos.
    labels = domain.split(".")
    if len(labels) >= 2:
        sld = labels[-2]
        tld = labels[-1]
        if tld in ("org", "com", "net", "biz", "info", "co", "io", "me"):
            return True
    return False


class DomainResolver:
    """Resolve a scholarship's official source URL to a trustworthy domain."""

    def __init__(self, registry: StaticSourceRegistry | None = None) -> None:
        self._registry = registry

    def resolve(
        self,
        official_source_url: str | None,
        scholarship_title: str | None = None,
        official_source_name: str | None = None,
    ) -> DomainResolution:
        evidence: list[str] = []
        domain = _extract_domain(official_source_url) if official_source_url else None

        if not domain:
            return DomainResolution(
                official_domain=None,
                is_official_domain=False,
                trust_score=0,
                source_type=None,
                resolution_method="no_url",
                confidence=DiscoveryConfidence.UNVERIFIED,
                evidence=evidence,
            )

        # 1. Registry lookup (exact domain).
        registry_entry: ApprovedSourceData | None = None
        if self._registry is not None:
            for s in self._registry.get_all_active():
                if s.domain == domain:
                    registry_entry = s
                    evidence.append(f"registry_exact:{s.domain}")
                    break

        if registry_entry is None and self._registry is not None:
            for s in self._registry.get_all_active():
                if domain == s.domain or domain.endswith("." + s.domain):
                    registry_entry = s
                    evidence.append(f"registry_suffix:{s.domain}")
                    break

        if registry_entry is not None:
            return DomainResolution(
                official_domain=registry_entry.domain,
                is_official_domain=True,
                trust_score=registry_entry.trust_score,
                source_type=registry_entry.source_type,
                resolution_method="registry",
                confidence=DiscoveryConfidence.HIGH,
                evidence=evidence,
            )

        # 2. Static official-domain check (government/edu suffixes only).
        # Deliberately EXCLUDES .org/.com/.net: those are not inherently official
        # and must not be treated as trustworthy without registry confirmation.
        if is_official_domain(domain) and not _is_non_official_tld(domain):
            evidence.append("official_suffix_match")
            return DomainResolution(
                official_domain=domain,
                is_official_domain=True,
                trust_score=70,
                source_type="official_university",
                resolution_method="official_suffix",
                confidence=DiscoveryConfidence.MEDIUM,
                evidence=evidence,
            )

        # 3. Provider name fallback (best-effort).
        if official_source_name:
            for src in _DEFAULT_SOURCES:
                if src.name.lower() == official_source_name.lower():
                    evidence.append(f"provider_name_match:{src.name}")
                    return DomainResolution(
                        official_domain=src.domain,
                        is_official_domain=True,
                        trust_score=src.trust_score,
                        source_type=src.source_type,
                        resolution_method="provider_name",
                        confidence=DiscoveryConfidence.MEDIUM,
                        evidence=evidence,
                    )

        # 4. Not resolvable to a known official source.
        return DomainResolution(
            official_domain=domain,
            is_official_domain=False,
            trust_score=0,
            source_type=None,
            resolution_method="unknown_domain",
            confidence=DiscoveryConfidence.UNVERIFIED,
            evidence=evidence + ["not_in_registry_and_not_official_suffix"],
        )


class PageRelevanceScorer:
    """Score a discovered page for relevance to a scholarship title."""

    def __init__(self, scholarship_title: str | None = None) -> None:
        self._title_tokens = tokenize(scholarship_title)
        self._title_lower = (scholarship_title or "").lower()

    def score_url(self, url: str, snippet: str | None = None, title: str | None = None) -> float:
        score = 0.0
        path = path_lower(url)

        path_tokens = set(tokenize(path))
        if self._title_tokens:
            overlap = sum(1 for t in self._title_tokens if t in path_tokens)
            score += 0.45 * (overlap / len(self._title_tokens))

        text = " ".join(filter(None, [snippet or "", title or ""]))
        if self._title_tokens and text:
            score += 0.35 * token_overlap_score(self._title_tokens, text)

        if self._title_lower and self._title_lower in (text or "").lower():
            score += 0.2

        for pat in ANNOUNCEMENT_PATH_PATTERNS:
            if pat in path:
                score += 0.05
                break

        if is_non_trustworthy_path(url):
            score -= 0.5

        return max(0.0, min(1.0, score))

    def score_candidate(self, candidate: OfficialPageCandidate) -> float:
        return self.score_url(candidate.url, candidate.snippet, candidate.title)



"""Chunk 5: OfficialPageDiscoveryService (part 1 - helpers)."""


import time
from typing import TYPE_CHECKING


def _html_title(content: str | None) -> str | None:
    if not content:
        return None
    low = content.lower()
    i = low.find("<title")
    if i < 0:
        return None
    j = low.find(">", i)
    if j < 0:
        return None
    end = low.find("</title>", j)
    if end < 0:
        return None
    text = content[j + 1:end].strip()
    return text or None


def _html_meta_description(content: str | None) -> str | None:
    if not content:
        return None
    low = content.lower()
    i = low.find("name=\"description\"")
    if i < 0:
        i = low.find("name='description'")
    if i < 0:
        return None
    j = low.find("content=", i)
    if j < 0:
        return None
    j += len("content=")
    quote = content[j] if j < len(content) else '"'
    k = content.find(quote, j + 1)
    if k < 0:
        return None
    text = content[j + 1:k].strip()
    return text or None


def _html_links(content: str | None, base_url: str) -> list[str]:
    """Extract href links from HTML content."""

    links: list[str] = []
    if not content:
        return links
    low = content.lower()
    idx = 0
    while True:
        i = low.find("<a", idx)
        if i < 0:
            break
        j = low.find(">", i)
        if j < 0:
            break
        tag = content[i:j]
        href_i = tag.lower().find("href=")
        if href_i < 0:
            idx = j + 1
            continue
        rest = tag[href_i + 5:].lstrip()
        if not rest:
            idx = j + 1
            continue
        quote = rest[0]
        if quote not in ('"', "'"):
            end = len(rest)
            for sep in (" ", ">", "\t", "\n"):
                pos = rest.find(sep)
                if pos > 0:
                    end = min(end, pos)
            raw = rest[:end]
        else:
            k = rest.find(quote, 1)
            raw = rest[1:k] if k > 0 else rest[1:]
        joined = join_url(base_url, raw.strip())
        if joined:
            links.append(joined)
        idx = j + 1
    return links


def _classify_page_kind(url: str, title: str | None, snippet: str | None) -> PageKind:
    path = path_lower(url)
    text = " ".join(filter(None, [title or "", snippet or ""])).lower()

    press_markers = ("press", "media", "newsroom")
    news_markers = ("news", "article", "story", "blog", "update", "alert")
    announcement_markers = ("announcement", "notice", "call", "open", "apply", "deadline")
    scholarship_markers = ("scholarship", "fellowship", "grant", "award", "funding", "program", "programme", "opportunity")

    if any(m in path for m in press_markers) or any(m in text[:120] for m in press_markers):
        return PageKind.PRESS
    if any(m in path for m in news_markers) or any(m in text[:120] for m in news_markers):
        return PageKind.NEWS
    if any(m in path for m in announcement_markers) or any(m in text[:120] for m in announcement_markers):
        return PageKind.ANNOUNCEMENT
    if any(m in path for m in scholarship_markers) or any(m in text[:120] for m in scholarship_markers):
        return PageKind.SCHOLARSHIP_PAGE
    if is_root_url(url):
        return PageKind.ROOT_DOMAIN
    return PageKind.UNKNOWN



"""Chunk 6: OfficialPageDiscoveryService (part 2 - sitemap discovery)."""


from typing import TYPE_CHECKING


def _candidate_sitemap_urls(root_url: str, source_domain: str) -> list[str]:
    """Build candidate sitemap URLs for a root domain."""
    from urllib.parse import urljoin

    urls: list[str] = []
    seen: set[str] = set()
    for name in SITEMAP_FILENAMES:
        joined = urljoin(root_url, name)
        canon = canonicalize_url(joined)
        if canon and canon not in seen:
            seen.add(canon)
            urls.append(canon)
    return urls


def _extract_sitemap_urls(content: str | None, base_url: str) -> list[str]:
    """Extract <loc> URLs from an XML sitemap."""

    urls: list[str] = []
    if not content:
        return urls
    low = content.lower()
    idx = 0
    while True:
        i = low.find("<loc", idx)
        if i < 0:
            break
        j = low.find(">", i)
        if j < 0:
            break
        inner = content[i + 4:j].strip()
        close = inner.lower().find("</loc>")
        if close > 0:
            inner = inner[:close]
        # strip attributes
        gt = inner.find(">")
        if gt > 0:
            inner = inner[gt + 1:]
        inner = inner.strip()
        if inner:
            joined = join_url(base_url, inner)
            if joined:
                urls.append(joined)
        idx = j + 1
    return urls


def _is_sitemap_url(url: str) -> bool:
    path = path_lower(url)
    return any(name in path for name in SITEMAP_FILENAMES)


def _discovery_sitemaps(
    discovery: "ImageDiscoveryService",
    root_url: str,
    source_domain: str,
    max_sitemaps: int = 3,
) -> tuple[list[str], list[str]]:
    """Discover sitemap URLs for a domain. Returns (sitemap_urls, fetched_urls)."""
    fetched: list[str] = []
    candidates = _candidate_sitemap_urls(root_url, source_domain)
    found: list[str] = []
    for cand in candidates:
        if len(found) >= max_sitemaps:
            break
        result = discovery.fetch_page(cand)
        fetched.append(cand)
        if result.error or not result.content:
            continue
        if result.status_code and result.status_code >= 400:
            continue
        if not _is_sitemap_url(cand) and "urlset" not in (result.content or "").lower() and "<loc" not in (result.content or "").lower():
            continue
        urls = _extract_sitemap_urls(result.content, result.url or cand)
        for u in urls:
            if u not in found:
                found.append(u)
    return found, fetched



"""Chunk 7: OfficialPageDiscoveryService (part 3 - page discovery core)."""


import time
from typing import TYPE_CHECKING


def _make_candidate(
    url: str,
    source_domain: str,
    is_official_domain: bool,
    trust_score: int,
    page_kind: PageKind,
    discovery_method: str,
    title: str | None = None,
    snippet: str | None = None,
    crawl_depth: int = 0,
    http_status: int | None = None,
    fetch_error: str | None = None,
    provenance: dict | None = None,
    evidence: list[str] | None = None,
) -> OfficialPageCandidate:
    return OfficialPageCandidate(
        url=url,
        normalized_url=canonicalize_url(url),
        page_kind=page_kind,
        source_domain=source_domain,
        is_official_domain=is_official_domain,
        trust_score=trust_score,
        relevance_score=0.0,
        confidence=DiscoveryConfidence.UNVERIFIED,
        discovery_method=discovery_method,
        title=title,
        snippet=snippet,
        crawl_depth=crawl_depth,
        http_status=http_status,
        fetch_error=fetch_error,
        is_trustworthy=False,
        provenance=provenance or {},
        evidence=evidence or [],
    )


def _score_and_classify(
    candidate: OfficialPageCandidate,
    scorer: PageRelevanceScorer,
    official_domain: str | None,
    is_official_domain: bool,
    trust_score: int,
) -> OfficialPageCandidate:
    relevance = scorer.score_url(candidate.url, candidate.snippet, candidate.title)
    # Trust bonus for official domain pages.
    if is_official_domain and candidate.is_official_domain:
        relevance = min(1.0, relevance + 0.15)
    if candidate.page_kind in (PageKind.SCHOLARSHIP_PAGE, PageKind.ANNOUNCEMENT):
        relevance = min(1.0, relevance + 0.1)

    if is_official_domain and candidate.is_official_domain and relevance >= 0.3:
        confidence = DiscoveryConfidence.HIGH
        trustworthy = True
    elif candidate.is_official_domain and relevance >= 0.15:
        confidence = DiscoveryConfidence.MEDIUM
        trustworthy = True
    elif relevance >= 0.5:
        confidence = DiscoveryConfidence.MEDIUM
        trustworthy = False
    elif relevance >= 0.2:
        confidence = DiscoveryConfidence.LOW
        trustworthy = False
    else:
        confidence = DiscoveryConfidence.UNVERIFIED
        trustworthy = False

    # Non-trustworthy path always loses trust.
    if is_non_trustworthy_path(candidate.url):
        trustworthy = False
        confidence = DiscoveryConfidence.LOW if confidence == DiscoveryConfidence.HIGH else confidence

    return OfficialPageCandidate(
        url=candidate.url,
        normalized_url=candidate.normalized_url,
        page_kind=candidate.page_kind,
        source_domain=candidate.source_domain,
        is_official_domain=candidate.is_official_domain,
        trust_score=candidate.trust_score,
        relevance_score=round(relevance, 4),
        confidence=confidence,
        discovery_method=candidate.discovery_method,
        title=candidate.title,
        snippet=candidate.snippet,
        crawl_depth=candidate.crawl_depth,
        http_status=candidate.http_status,
        fetch_error=candidate.fetch_error,
        is_trustworthy=trustworthy,
        provenance=candidate.provenance,
        evidence=candidate.evidence,
    )



"""Chunk 8: discover root domain page."""


from typing import TYPE_CHECKING


def _discover_root_page(
    discovery: "ImageDiscoveryService",
    root_url: str,
    source_domain: str,
    is_official_domain: bool,
    trust_score: int,
    scorer,
) -> OfficialPageCandidate | None:
    result = discovery.fetch_page(root_url)
    if result.error or not result.content:
        return None
    title = _html_title(result.content)
    snippet = _html_meta_description(result.content)
    cand = _make_root_candidate(
        root_url, source_domain, is_official_domain, trust_score, title, snippet, result.status_code
    )
    return _score_and_classify(cand, scorer, source_domain, is_official_domain, trust_score)


def _make_root_candidate(
    url, source_domain, is_official_domain, trust_score, title, snippet, status_code
):
    return OfficialPageCandidate(
        url=url,
        normalized_url=canonicalize_url(url),
        page_kind=PageKind.ROOT_DOMAIN,
        source_domain=source_domain,
        is_official_domain=is_official_domain,
        trust_score=trust_score,
        relevance_score=0.0,
        confidence=DiscoveryConfidence.UNVERIFIED,
        discovery_method="root_domain_fetch",
        title=title,
        snippet=snippet,
        crawl_depth=0,
        http_status=status_code,
        fetch_error=None,
        is_trustworthy=False,
        provenance={"fetched": True},
        evidence=["root_domain"],
    )



"""Chunk 9: discover common official paths on a root domain."""


from typing import TYPE_CHECKING


def _discover_common_paths(
    discovery: "ImageDiscoveryService",
    root_url: str,
    source_domain: str,
    is_official_domain: bool,
    trust_score: int,
    scorer,
    max_paths: int = 12,
) -> list:
    """Probe a bounded list of common official sub-paths on the root domain."""
    from urllib.parse import urljoin

    results = []
    seen = set()
    for path in COMMON_OFFICIAL_PATHS:
        if len(results) >= max_paths:
            break
        joined = urljoin(root_url, path)
        canon = canonicalize_url(joined)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        result = discovery.fetch_page(canon)
        if result.error or not result.content:
            continue
        if result.status_code and result.status_code >= 400:
            continue
        title = _html_title(result.content)
        snippet = _html_meta_description(result.content)
        kind = _classify_page_kind(canon, title, snippet)
        cand = _make_candidate(
            canon, source_domain, is_official_domain, trust_score, kind,
            "common_path_probe", title=title, snippet=snippet,
            http_status=result.status_code,
            provenance={"probed_path": path},
            evidence=[f"common_path:{path}"],
        )
        results.append(_score_and_classify(cand, scorer, source_domain, is_official_domain, trust_score))
    return results



"""Chunk 10: in-domain scholarship-title search."""


from typing import TYPE_CHECKING


def _in_domain_search(
    discovery: "ImageDiscoveryService",
    root_url: str,
    source_domain: str,
    scholarship_title: str,
    is_official_domain: bool,
    trust_score: int,
    scorer,
    max_links: int = 15,
) -> list:
    """Search within the official domain for pages mentioning the scholarship title."""

    results = []
    root_result = discovery.fetch_page(root_url)
    if root_result.error or not root_result.content:
        return results

    links = _html_links(root_result.content, root_result.url or root_url)
    title_tokens = [t.lower() for t in (scholarship_title or "").split() if len(t) > 2]
    scored_links = []
    for link in links:
        if not _same_domain(link, source_domain):
            continue
        canon = canonicalize_url(link)
        if not canon:
            continue
        score = 0.0
        link_lower = canon.lower()
        for tok in title_tokens:
            if tok in link_lower:
                score += 1.0
        if score <= 0:
            continue
        scored_links.append((score, canon))

    scored_links.sort(key=lambda x: x[0], reverse=True)
    for score, canon in scored_links[:max_links]:
        result = discovery.fetch_page(canon)
        if result.error or not result.content:
            continue
        if result.status_code and result.status_code >= 400:
            continue
        title = _html_title(result.content)
        snippet = _html_meta_description(result.content)
        kind = _classify_page_kind(canon, title, snippet)
        cand = _make_candidate(
            canon, source_domain, is_official_domain, trust_score, kind,
            "in_domain_title_match", title=title, snippet=snippet,
            http_status=result.status_code,
            provenance={"title_token_score": score},
            evidence=[f"in_domain_title_match:score={score}"],
        )
        results.append(_score_and_classify(cand, scorer, source_domain, is_official_domain, trust_score))
    return results


def _same_domain(url: str, domain: str) -> bool:
    return is_same_domain(url, domain)



"""Chunk 11: announcement/news/press discovery."""


from typing import TYPE_CHECKING


ANNOUNCEMENT_KEYWORDS = (
    "announcement", "news", "press", "media", "story", "article",
    "blog", "update", "alert", "notice", "event", "activity",
    "result", "outcome", "deadline", "open", "call",
)


def _discover_announcements(
    discovery: "ImageDiscoveryService",
    root_url: str,
    source_domain: str,
    is_official_domain: bool,
    trust_score: int,
    scorer,
    max_pages: int = 10,
) -> list:
    """Discover announcement/news/press pages by crawling root links."""
    root_result = discovery.fetch_page(root_url)
    if root_result.error or not root_result.content:
        return []

    links = _html_links(root_result.content, root_result.url or root_url)
    results = []
    seen = set()
    for link in links:
        if len(results) >= max_pages:
            break
        canon = canonicalize_url(link)
        if not canon or canon in seen:
            continue
        if not _same_domain(canon, source_domain):
            continue
        path = canon.lower()
        if not any(k in path for k in ANNOUNCEMENT_KEYWORDS):
            continue
        seen.add(canon)
        result = discovery.fetch_page(canon)
        if result.error or not result.content:
            continue
        if result.status_code and result.status_code >= 400:
            continue
        title = _html_title(result.content)
        snippet = _html_meta_description(result.content)
        kind = _classify_page_kind(canon, title, snippet)
        cand = _make_candidate(
            canon, source_domain, is_official_domain, trust_score, kind,
            "announcement_news_press_crawl", title=title, snippet=snippet,
            http_status=result.status_code,
            provenance={"discovery_group": "announcement_news_press"},
            evidence=["announcement_news_press_crawl"],
        )
        results.append(_score_and_classify(cand, scorer, source_domain, is_official_domain, trust_score))
    return results


def _same_domain(url: str, domain: str) -> bool:
    return is_same_domain(url, domain)



"""Chunk 12: OfficialPageDiscoveryService main class."""


import time
from typing import TYPE_CHECKING


class OfficialPageDiscoveryService:
    """Discover trustworthy official pages for a scholarship record.

    The service is read-only: it discovers and scores pages but does not
    mutate the database. Persistence decisions belong to the orchestrator.
    """

    def __init__(
        self,
        discovery: "ImageDiscoveryService | None" = None,
        registry: "StaticSourceRegistry | None" = None,
        max_pages_per_scholarship: int = DEFAULT_MAX_PAGES_PER_SCHOLARSHIP,
        max_requests_per_scholarship: int = DEFAULT_MAX_REQUESTS_PER_SCHOLARSHIP,
        max_crawl_depth: int = DEFAULT_MAX_CRAWL_DEPTH,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        request_interval: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    ) -> None:
        self._discovery = discovery
        self._registry = registry
        self._max_pages = max_pages_per_scholarship
        self._max_requests = max_requests_per_scholarship
        self._max_depth = max_crawl_depth
        self._timeout = timeout_seconds
        self._interval = request_interval
        self._domain_resolver = DomainResolver(registry)

    def _get_discovery(self) -> "ImageDiscoveryService":
        if self._discovery is not None:
            return self._discovery
        from .image_discovery import ImageDiscoveryService
        return ImageDiscoveryService(timeout=self._timeout)

    def discover(
        self,
        scholarship_id: int | None,
        scholarship_title: str | None,
        official_source_url: str | None,
        official_source_name: str | None = None,
    ) -> DiscoveryOutcome:
        title = scholarship_title or ""
        resolution = self._domain_resolver.resolve(official_source_url, title, official_source_name)
        scorer = PageRelevanceScorer(title)

        outcome = DiscoveryOutcome(
            scholarship_id=scholarship_id,
            scholarship_title=title,
            official_source_url=official_source_url,
            official_domain=resolution.official_domain,
            is_official_domain=resolution.is_official_domain,
        )

        if not official_source_url or not resolution.official_domain:
            outcome.error = "no_official_source_url"
            return outcome

        discovery = self._get_discovery()
        start = time.time()
        root_url = canonicalize_url(official_source_url)
        if not root_url:
            root_url = canonicalize_url("https://" + resolution.official_domain)
        if not root_url:
            outcome.error = "cannot_build_root_url"
            return outcome

        # 1. Root domain page.
        root_cand = _discover_root_page(
            discovery, root_url, resolution.official_domain,
            resolution.is_official_domain, resolution.trust_score, scorer,
        )
        if root_cand is not None:
            outcome.candidates.append(root_cand)
            outcome.pages_fetched += 1
            outcome.requests_made += 1

        # 2. Sitemaps.
        sitemap_urls, sitemap_fetched = _discovery_sitemaps(
            discovery, root_url, resolution.official_domain,
        )
        outcome.sitemaps_found = sitemap_urls
        outcome.requests_made += len(sitemap_fetched)

        # 3. Common official paths.
        common = _discover_common_paths(
            discovery, root_url, resolution.official_domain,
            resolution.is_official_domain, resolution.trust_score, scorer,
        )
        outcome.candidates.extend(common)
        outcome.pages_fetched += len(common)
        outcome.requests_made += len(common)

        # 4. In-domain title search.
        in_domain = _in_domain_search(
            discovery, root_url, resolution.official_domain, title,
            resolution.is_official_domain, resolution.trust_score, scorer,
        )
        outcome.candidates.extend(in_domain)
        outcome.pages_fetched += len(in_domain)
        outcome.requests_made += len(in_domain)

        # 5. Announcement/news/press discovery.
        announcements = _discover_announcements(
            discovery, root_url, resolution.official_domain,
            resolution.is_official_domain, resolution.trust_score, scorer,
        )
        outcome.candidates.extend(announcements)
        outcome.pages_fetched += len(announcements)
        outcome.requests_made += len(announcements)

        # Deduplicate and bound.
        seen = set()
        unique = []
        for c in outcome.candidates:
            if c.normalized_url in seen:
                continue
            seen.add(c.normalized_url)
            unique.append(c)
        outcome.candidates = unique[: self._max_pages]

        # Separate trustworthy candidates.
        outcome.trusted_candidates = [c for c in outcome.candidates if c.is_trustworthy]

        if time.time() - start > self._timeout:
            outcome.timed_out = True
        if outcome.requests_made >= self._max_requests:
            outcome.bounded = True
        return outcome


