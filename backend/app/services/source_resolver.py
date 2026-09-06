"""Source URL resolution for scholarship image discovery.

Classifies and resolves official_source_url values to program-specific pages
when the URL is a root domain. Uses evidence from same-domain crawling to
find the most relevant program page via keyword matching and page metadata.

Read-only: never modifies database records.
"""

from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


class SourceResolutionType(str, Enum):
    EXACT_PROGRAM_PAGE = "exact_program_page"
    OFFICIAL_APPLICATION_PAGE = "official_application_page"
    OFFICIAL_UNIVERSITY_PAGE = "official_university_page"
    OFFICIAL_PROVIDER_PAGE = "official_provider_page"
    ROOT_DOMAIN = "root_domain"
    INVALID = "invalid"
    INACCESSIBLE = "inaccessible"


@dataclass
class ResolvedSource:
    original_url: str
    resolved_url: str | None
    resolution_type: SourceResolutionType
    confidence: float
    reason: str
    page_title: str | None = None
    page_h1: str | None = None
    matched_keywords: list[str] = field(default_factory=list)
    alternatives: list[tuple[str, float]] = field(default_factory=list)


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

PAGE_FETCH_TIMEOUT = 15.0
MAX_ROUTES_TO_CHECK = 20
LINK_KEYWORDS = (
    "scholarship", "scholarships", "program", "programme",
    "study-abroad", "study-abroad-program", "international",
    "financial-aid", "funding", "grant", "exchange",
    "study", "opportunity", "bourse", "beasisik",
    "stipendium", "beca", "stipend", "fellowship",
    "application", "apply", "admission", "entrance",
)

WEAK_PAGE_PENALTIES = (
    "notification", "announcement", "news", "press",
    "search", "result", "list", "listing", "archive",
    "sitemap", "index", "about", "contact", "privacy",
    "terms", "policy", "cookie", "accessibility",
    "login", "register", "signin", "signup",
    "blog", "article", "post", "media",
    "event", "calendar", "agenda",
)

_SCHEMELESS_PREFIXES = (
    "http://", "https://",
)


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url.lower().startswith(_SCHEMELESS_PREFIXES):
        url = "https://" + url
    return url


def _extract_domain(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.netloc.lower() if parsed.netloc else None


def _extract_path_segments(url: str) -> list[str]:
    parsed = urlparse(url)
    return [s for s in parsed.path.split("/") if s and s not in ("index.html", "index.htm", "")]


PROGRAM_PAGE_KEYWORDS = (
    "scholarship", "scholarships", "program", "programme",
    "financial-aid", "funding", "fellowship", "stipendium",
    "application", "apply", "grant", "exchange", "opportunity",
)

WEAK_PAGE_KEYWORDS = (
    "notification", "announcement", "news", "press",
    "search", "result", "list", "listing", "sitemap",
    "about", "contact", "privacy", "terms", "policy",
    "blog", "article", "post", "event", "calendar",
)


def _classify_url(url: str) -> SourceResolutionType:
    if not url or not url.strip():
        return SourceResolutionType.INVALID
    try:
        normalized = _normalize_url(url)
        parsed = urlparse(normalized)
    except Exception:
        return SourceResolutionType.INVALID

    if not parsed.scheme.startswith("http"):
        return SourceResolutionType.INVALID
    if not parsed.netloc:
        return SourceResolutionType.INVALID

    path = parsed.path.lower()
    path_segs = [s for s in path.split("/") if s and s not in ("index.html", "index.htm", "")]

    if len(path_segs) == 0:
        return SourceResolutionType.ROOT_DOMAIN

    is_weak = any(kw in path for kw in WEAK_PAGE_KEYWORDS)
    is_program = any(kw in path for kw in PROGRAM_PAGE_KEYWORDS)

    if len(path_segs) >= 2 and is_program and not is_weak:
        return SourceResolutionType.EXACT_PROGRAM_PAGE

    if len(path_segs) >= 2 and is_weak:
        return SourceResolutionType.ROOT_DOMAIN

    if len(path_segs) >= 2:
        return SourceResolutionType.OFFICIAL_APPLICATION_PAGE

    if len(path_segs) == 1 and is_program:
        return SourceResolutionType.OFFICIAL_APPLICATION_PAGE

    if len(path_segs) == 1 and is_weak:
        return SourceResolutionType.ROOT_DOMAIN

    return SourceResolutionType.OFFICIAL_APPLICATION_PAGE


class SourceResolverService:
    """Resolves official_source_url to program-specific pages when possible."""

    def __init__(self, timeout: float = PAGE_FETCH_TIMEOUT, max_routes: int = MAX_ROUTES_TO_CHECK):
        self.timeout = timeout
        self.max_routes = max_routes
        self._page_cache: dict[str, tuple[str, str, str]] = {}
        self._domain_cache: dict[str, bool] = {}

    def resolve_source(
        self,
        official_source_url: str,
        scholarship_title: str | None = None,
    ) -> ResolvedSource:
        """Resolve a source URL, attempting to find a program-specific page."""
        if not official_source_url or not official_source_url.strip():
            return ResolvedSource(
                original_url=official_source_url or "",
                resolved_url=None,
                resolution_type=SourceResolutionType.INVALID,
                confidence=0.0,
                reason="URL is empty or whitespace",
            )

        try:
            normalized = _normalize_url(official_source_url)
        except Exception:
            return ResolvedSource(
                original_url=official_source_url,
                resolved_url=None,
                resolution_type=SourceResolutionType.INVALID,
                confidence=0.0,
                reason="URL normalization failed",
            )

        classification = _classify_url(normalized)

        if classification in (SourceResolutionType.EXACT_PROGRAM_PAGE,
                              SourceResolutionType.OFFICIAL_APPLICATION_PAGE,
                              SourceResolutionType.OFFICIAL_UNIVERSITY_PAGE,
                              SourceResolutionType.OFFICIAL_PROVIDER_PAGE):
            return ResolvedSource(
                original_url=official_source_url,
                resolved_url=normalized,
                resolution_type=classification,
                confidence=0.95,
                reason=f"Source URL is already {classification.value}",
            )

        if classification == SourceResolutionType.INVALID:
            return ResolvedSource(
                original_url=official_source_url,
                resolved_url=None,
                resolution_type=SourceResolutionType.INVALID,
                confidence=0.0,
                reason="Malformed or invalid URL",
            )

        if classification == SourceResolutionType.ROOT_DOMAIN:
            return self._resolve_root_domain(
                normalized, scholarship_title or "",
            )

        return ResolvedSource(
            original_url=official_source_url,
            resolved_url=normalized,
            resolution_type=SourceResolutionType.ROOT_DOMAIN,
            confidence=0.3,
            reason="URL classification unclear",
        )

    def _resolve_root_domain(self, root_url: str, title: str) -> ResolvedSource:
        """Attempt to find a program-specific page from a root domain."""
        page_result = self._fetch_cached_page(root_url)
        if page_result is None:
            return ResolvedSource(
                original_url=root_url,
                resolved_url=None,
                resolution_type=SourceResolutionType.INACCESSIBLE,
                confidence=0.0,
                reason="Root domain page is inaccessible (HTTP error or timeout)",
            )

        status_code, content, _ = page_result
        if status_code != 200 or not content:
            return ResolvedSource(
                original_url=root_url,
                resolved_url=None,
                resolution_type=SourceResolutionType.INACCESSIBLE,
                confidence=0.0,
                reason=f"Root domain returned HTTP {status_code}",
            )

        soup = BeautifulSoup(content, "html.parser")
        title_text = soup.find("title")
        h1_text = soup.find("h1")
        page_title = title_text.get_text(strip=True)[:200] if title_text else None
        page_h1 = h1_text.get_text(strip=True)[:200] if h1_text else None

        candidates = self._extract_relevant_links(soup, root_url, title)

        if not candidates:
            return ResolvedSource(
                original_url=root_url,
                resolved_url=None,
                resolution_type=SourceResolutionType.ROOT_DOMAIN,
                confidence=0.1,
                reason="Root domain has no program/scholarship links found via keyword matching",
                page_title=page_title,
                page_h1=page_h1,
            )

        candidates.sort(key=lambda x: x[1], reverse=True)

        best_url = candidates[0][0]
        best_score = candidates[0][1]

        if best_score >= 0.6:
            resolution_type = SourceResolutionType.EXACT_PROGRAM_PAGE
            confidence = round(best_score * 0.95, 4)
            reason = f"Found high-confidence program link from root domain (score={best_score:.2f})"
        elif best_score >= 0.4:
            resolution_type = SourceResolutionType.OFFICIAL_APPLICATION_PAGE
            confidence = round(best_score * 0.85, 4)
            reason = f"Found moderate-confidence application link from root domain (score={best_score:.2f})"
        else:
            resolution_type = SourceResolutionType.ROOT_DOMAIN
            confidence = 0.15
            reason = f"Best link score ({best_score}) too low for reliable resolution — weak match"

        alternatives = [(url, score) for url, score in candidates[:5]]

        return ResolvedSource(
            original_url=root_url,
            resolved_url=best_url if confidence > 0.2 else None,
            resolution_type=resolution_type,
            confidence=confidence,
            reason=reason,
            page_title=page_title,
            page_h1=page_h1,
            alternatives=alternatives,
        )

    def _extract_relevant_links(self, soup: BeautifulSoup, base_url: str, title: str) -> list[tuple[str, float]]:
        """Extract program-relevant links from a page, scored by keyword match and title relevance."""
        base_domain = _extract_domain(base_url)
        if not base_domain:
            return []

        title_words = _tokenize_title(title)

        canonical_url = None
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        if canonical_tag and canonical_tag.get("href"):
            canonical_url = urljoin(base_url, canonical_tag["href"].strip())

        page_title_tag = soup.find("title")
        page_title_text = page_title_tag.get_text(strip=True).lower() if page_title_tag else ""
        h1_tag = soup.find("h1")
        h1_text = h1_tag.get_text(strip=True).lower() if h1_tag else ""

        links = []
        seen_urls: set[str] = set()

        for a in soup.find_all("a", href=True):
            if len(links) >= self.max_routes:
                break

            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc.lower() != base_domain:
                continue
            if full_url in seen_urls:
                continue
            if canonical_url and full_url == canonical_url:
                continue

            path_lower = parsed.path.lower()
            link_text = a.get_text(strip=True).lower()

            score = 0.0
            matched = []

            keyword_hits = 0
            for kw in LINK_KEYWORDS:
                if kw in path_lower or kw in link_text:
                    keyword_hits += 1
                    matched.append(kw)

            if keyword_hits > 0:
                score += min(keyword_hits * 0.25, 0.5)

            for word in title_words:
                if word in path_lower or word in link_text:
                    score += 0.15
                    if word not in matched:
                        matched.append(word)

            title_hits = sum(1 for w in title_words if w in page_title_text or w in path_lower or w in link_text)
            if title_hits >= 2:
                score += 0.1
                if "page_title" not in matched:
                    matched.append("page_title")

            is_weak = any(kw in path_lower for kw in WEAK_PAGE_PENALTIES)
            if is_weak:
                score *= 0.25
                matched.append("weak_page_penalty")

            if len(matched) >= 3 and not is_weak:
                score += 0.1

            score = min(score, 1.0)

            if score > 0:
                links.append((full_url, round(score, 4)))
                seen_urls.add(full_url)

        return links

    def _fetch_cached_page(self, url: str) -> tuple[int, str | None, str | None] | None:
        """Fetch a page with caching. Returns (status, content, error) or None."""
        if url in self._page_cache:
            return self._page_cache[url]

        try:
            response = httpx.get(
                url,
                headers={"User-Agent": BROWSER_UA, "Accept": "text/html"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    result = (response.status_code, response.text, None)
                else:
                    result = (response.status_code, None, f"Non-HTML content-type: {content_type}")
            else:
                result = (response.status_code, None, f"HTTP {response.status_code}")
        except httpx.RequestError as exc:
            result = (None, None, str(exc))
        except Exception as exc:
            result = (None, None, str(exc))

        self._page_cache[url] = result
        return result


def _tokenize_title(title: str) -> list[str]:
    """Tokenize a scholarship title into searchable lowercase words."""
    if not title:
        return []
    result = []
    for word in title.lower().split():
        word = word.strip("(),.:/-")
        if len(word) >= 4 and word not in _STOPWORDS:
            result.append(word)
    return result


_STOPWORDS = frozenset({
    "the", "and", "for", "with", "from", "this", "that",
    "your", "have", "will", "will", "into", "than", "then",
    "have", "has", "had", "are", "was", "were", "been",
    "international", "global", "world", "wide",
})
