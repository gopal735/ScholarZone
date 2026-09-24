"""Evidence-driven image discovery from official scholarship source URLs.

Discovers candidate image URLs by scraping the scholarship's
official_source_url and following same-domain links to relevant
sub-pages (program pages, application pages, etc.).

Discovery tiers (exhausted in order):
   1. Canonical official_source_url
   2. Relevant official scholarship/program pages on the same domain
   3. Official provider/government/university pages on known official domains
   4. HTML image assets actually referenced by authoritative pages
   5. Open Graph / social preview image metadata
   6. Structured metadata (JSON-LD)
   7. Official domain asset paths (common logo/banner paths)
   8. Official logo as FINAL FALLBACK (link rel=icon, apple-touch-icon)

Designed for read-only dry-run validation — never writes to the database.
"""

import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from ..services.scholarship_image_verifier import ImageSourceType, is_official_domain


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

MAX_PAGES_PER_SOURCE = 25
MAX_CANDIDATES = 50
MAX_CRAWL_DEPTH = 2
SCHOLARSHIP_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 2
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
TRANSIENT_BLOCKED_CODES = {403, 412}
ENHANCED_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

_TRACKING_QUERY_PARAMETERS = frozenset({
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
})

_DISCOVERY_METHOD_PRIORITY = {
    "html-img": 0,
    "picture-source": 1,
    "link-image-src": 2,
    "css-background": 3,
    "json-ld": 4,
    "twitter:image": 5,
    "og:image": 6,
    "common-asset": 7,
    "link-rel-icon": 8,
}
JsonLdImageReference = tuple[str, str | None, str | None]


@dataclass
class ImageCandidate:
    image_url: str
    page_url: str
    discovery_method: str
    fallback_level: int = 1
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None
    file_size_estimate: int | None = None
    html_context: str | None = None
    normalized_url: str | None = None
    discovery_methods: list[str] = field(default_factory=list)
    source_attribute: str | None = None
    image_region: str | None = None
    provenance: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)

    @property
    def candidate_source_url(self) -> str:
        """The official page that directly referenced this candidate."""
        return self.page_url


@dataclass
class PageFetchResult:
    url: str
    status_code: int | None
    content: str | None
    error: str | None = None


class ImageDiscoveryService:
    """Discovers official image candidates from scholarship source URLs."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_candidates: int = MAX_CANDIDATES,
        max_retries: int = DEFAULT_MAX_RETRIES,
        scholarship_timeout: float = SCHOLARSHIP_TIMEOUT,
    ):
        self.timeout = timeout
        self.max_candidates = max_candidates
        self.max_retries = max_retries
        self.scholarship_timeout = scholarship_timeout
        self._seen_pages: set[str] = set()
        self._candidates: list[ImageCandidate] = []
        self._candidate_keys: set[str] = set()
        self._page_cache: dict[str, PageFetchResult] = {}
        self._start_time: float = 0.0
        self._requests_made: int = 0
        self._timeout_count: int = 0
        self._blocked_count: int = 0
        self._transient_error_count: int = 0
        self._source_url: str | None = None
        self._canonical_page_urls: set[str] = set()

    def _reset_state(self) -> None:
        self._seen_pages.clear()
        self._candidates.clear()
        self._candidate_keys.clear()
        self._page_cache.clear()
        self._start_time = time.time()
        self._requests_made = 0
        self._timeout_count = 0
        self._blocked_count = 0
        self._transient_error_count = 0
        self._source_url = None
        self._canonical_page_urls.clear()

    def discover_from_scholarship(self, official_source_url: str) -> list[ImageCandidate]:
        """Start discovery from a scholarship's canonical official_source_url.

        Exhausts all discovery tiers before returning.
        """
        self._reset_state()
        if not official_source_url:
            return []

        for _tier_name, _added in self.discover_tier_by_tier(official_source_url):
            pass
        return self._candidates[: self.max_candidates]

    def discover_tier_by_tier(self, official_source_url: str):
        """Yield candidate counts for each discovery tier.

        The generator keeps page fetching separate from extraction so callers can
        evaluate each source class independently. ``discover_from_scholarship``
        still uses the combined fast path.
        """
        self._reset_state()
        self._source_url = official_source_url
        self._canonical_page_urls.add(official_source_url)

        if not official_source_url:
            return

        source_domain = _extract_netloc(official_source_url)

        self._crawl_page(
            official_source_url,
            depth=0,
            fallback_level=1,
            source_domain=source_domain,
            extract_images=False,
            crawl_subpages=False,
        )
        yield "tier1_canonical_page", 0

        if self._is_timed_out():
            return

        added = self._discover_same_domain_program_pages(official_source_url, source_domain)
        yield "tier2_same_domain", added

        if self._is_timed_out():
            return

        added = self._discover_cross_domain_official_pages(official_source_url, source_domain)
        yield "tier3_cross_domain", added

        if self._is_timed_out():
            return

        added = self._extract_cached_page_images(
            official_source_url,
            source_domain,
            fallback_level=4,
            methods={"html-img", "picture-source", "link-image-src"},
        )
        yield "tier4_html_images", added

        added = self._extract_cached_page_images(
            official_source_url,
            source_domain,
            fallback_level=5,
            methods={"og:image", "twitter:image"},
        )
        yield "tier5_social_metadata", added

        added = self._extract_cached_page_images(
            official_source_url,
            source_domain,
            fallback_level=6,
            methods={"json-ld"},
        )
        yield "tier6_jsonld", added

        added = self._extract_cached_page_images(
            official_source_url,
            source_domain,
            fallback_level=6,
            methods={"css-background"},
        )
        yield "tier6_css_backgrounds", added

        if self._is_timed_out():
            return

        added = self._probe_common_asset_paths(official_source_url, source_domain)
        yield "tier7_common_assets", added

        if self._is_timed_out():
            return

        added = self._discover_logo_fallback(official_source_url, source_domain)
        yield "tier8_logo_fallback", added

    def _is_timed_out(self) -> bool:
        elapsed = time.time() - self._start_time
        return elapsed > self.scholarship_timeout

    def _record_request(self, result: PageFetchResult) -> None:
        self._requests_made += 1
        if result.status_code in (408, 429):
            self._timeout_count += 1
        elif result.status_code in (403,):
            self._blocked_count += 1
        elif result.status_code and result.status_code >= 500:
            self._transient_error_count += 1
        if result.error and "timeout" in result.error.lower():
            self._timeout_count += 1

    def _crawl_page(
        self,
        url: str,
        depth: int,
        fallback_level: int,
        source_domain: str,
        extract_images: bool = True,
        crawl_subpages: bool = True,
    ) -> int:
        if url in self._seen_pages:
            return 0
        if len(self._seen_pages) >= MAX_PAGES_PER_SOURCE:
            return 0
        if depth > MAX_CRAWL_DEPTH:
            return 0

        requested_domain = _extract_netloc(url)
        if not requested_domain or not is_official_domain(requested_domain):
            return 0

        result = self._fetch_page_cached(url)
        effective_url = result.url or url
        effective_domain = _extract_netloc(effective_url)
        if not effective_domain or not is_official_domain(effective_domain):
            return 0
        self._seen_pages.add(effective_url)
        if effective_url != url and url == self._source_url:
            self._canonical_page_urls.add(effective_url)
        if result.content is None:
            return 0

        initial_count = len(self._candidates)

        if extract_images:
            self._extract_images(
                result,
                effective_url,
                effective_domain,
                fallback_level,
                include_fallback_level_8=False,
            )

        if crawl_subpages and fallback_level <= 2:
            subpage_urls = self._extract_subpage_links(result, effective_url, effective_domain, depth)
            for sub_url in subpage_urls:
                if len(self._seen_pages) >= MAX_PAGES_PER_SOURCE:
                    break
                if self._is_timed_out():
                    break
                self._crawl_page(
                    sub_url,
                    depth + 1,
                    fallback_level=2,
                    source_domain=source_domain,
                )

        return len(self._candidates) - initial_count

    def _fetch_page_cached(self, url: str) -> PageFetchResult:
        if url not in self._page_cache:
            self._page_cache[url] = self._fetch_page(url)
        result = self._page_cache[url]
        if result.url and result.url != url:
            self._page_cache.setdefault(result.url, result)
        return result

    def _extract_cached_page_images(
        self,
        url: str,
        source_domain: str,
        fallback_level: int,
        methods: set[str],
    ) -> int:
        result = self._page_cache.get(url)
        if result is None or result.content is None:
            result = self._fetch_page_cached(url)
        if result.content is None:
            return 0
        initial_count = len(self._candidates)
        page_url = result.url or url
        self._extract_images(
            result,
            page_url,
            source_domain,
            fallback_level,
            include_fallback_level_8=False,
            methods=methods,
        )
        return len(self._candidates) - initial_count

    def _discover_same_domain_program_pages(self, official_source_url: str, source_domain: str) -> int:
        """Tier 2: Discover program pages on the same domain via sitemap and common paths."""
        if not source_domain:
            return 0

        parsed = urlparse(official_source_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        initial_count = len(self._candidates)
        seen_urls: set[str] = set()

        sitemap_urls = self._fetch_sitemap(f"{base_url}/sitemap.xml", source_domain)
        for sitemap_url in sitemap_urls[:5]:
            if sitemap_url in seen_urls:
                continue
            seen_urls.add(sitemap_url)
            if sitemap_url not in self._seen_pages and len(self._seen_pages) < MAX_PAGES_PER_SOURCE:
                if self._is_timed_out():
                    break
                self._crawl_page(sitemap_url, depth=0, fallback_level=2, source_domain=source_domain)

        common_paths = [
            "/programs", "/programmes", "/scholarships", "/scholarship",
            "/study", "/study-abroad", "/funding", "/grants", "/international",
            "/apply", "/application", "/admissions", "/degrees", "/courses",
            "/about", "/about-us", "/news", "/events", "/pages",
        ]
        for path in common_paths:
            if self._is_timed_out():
                break
            page_url = urljoin(base_url, path)
            if page_url in seen_urls:
                continue
            seen_urls.add(page_url)
            if page_url not in self._seen_pages and len(self._seen_pages) < MAX_PAGES_PER_SOURCE:
                self._crawl_page(page_url, depth=0, fallback_level=2, source_domain=source_domain)

        return len(self._candidates) - initial_count

    def _discover_cross_domain_official_pages(self, official_source_url: str, source_domain: str) -> int:
        """Tier 3: Follow links to known official domains (government, university, provider)."""
        if not official_source_url:
            return 0

        initial_count = len(self._candidates)
        result = self._fetch_page_cached(official_source_url)
        if result.content is None:
            return len(self._candidates) - initial_count

        page_url = result.url or official_source_url
        soup = BeautifulSoup(result.content, "html.parser")
        known_official_suffixes = [
            ".gov", ".go.kr", ".go.jp", ".ac.kr", ".ac.jp", ".ac.cn",
            ".edu", ".europa.eu", "erasmus-plus.ec.europa.eu",
            "daad.de", "iccr.gov.in", "studyinkorea.go.kr", "studyinjapan.go.jp",
            "campusfrance.org", "fulbrightonline.org", "educationusa.state.gov",
            "aefe.gouv.fr", "gouv.fr", "a-star.edu.sg", "nuffic.nl", "si.se",
            "esteri.it", "ec.europa.eu",
        ]

        cross_domain_urls: list[str] = []
        seen_urls: set[str] = set()
        for a in soup.find_all("a", href=True):
            if self._is_timed_out():
                break
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)
            if not parsed.scheme.startswith("http"):
                continue
            link_domain = parsed.netloc.lower()
            if link_domain == source_domain:
                continue
            if any(link_domain == suffix or link_domain.endswith(f".{suffix}") or suffix in link_domain
                   for suffix in known_official_suffixes):
                if full_url not in seen_urls and _is_page_url(full_url):
                    cross_domain_urls.append(full_url)
                    seen_urls.add(full_url)

        for cross_url in cross_domain_urls[:5]:
            if cross_url not in self._seen_pages and len(self._seen_pages) < MAX_PAGES_PER_SOURCE:
                if self._is_timed_out():
                    break
                self._crawl_page(cross_url, depth=0, fallback_level=3, source_domain=source_domain)

        return len(self._candidates) - initial_count

    def _probe_common_asset_paths(self, official_source_url: str, source_domain: str) -> int:
        """Tier 7: Probe common asset paths on the official domain."""
        if not source_domain:
            return 0

        parsed = urlparse(official_source_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        initial_count = len(self._candidates)

        common_paths = [
            "/logo.png", "/logo.svg", "/logo.jpg", "/logo.gif", "/logo.webp", "/logo.avif",
            "/images/logo.png", "/images/logo.svg", "/images/logo.jpg", "/images/logo.avif",
            "/assets/logo.png", "/assets/logo.svg", "/assets/logo.jpg", "/assets/logo.avif",
            "/img/logo.png", "/img/logo.jpg", "/img/logo.avif",
            "/banner.png", "/banner.jpg", "/banner.svg", "/banner.webp", "/banner.avif",
            "/images/banner.png", "/images/banner.jpg", "/images/banner.avif",
            "/header.jpg", "/header.png", "/header.avif",
            "/hero.jpg", "/hero.png", "/hero.avif",
            "/homepage-banner.jpg", "/homepage-banner.png", "/homepage-banner.avif",
            "/images/header.jpg", "/images/header.png", "/images/header.avif",
            "/images/hero.jpg", "/images/hero.png", "/images/hero.avif",
        ]

        for path in common_paths:
            if len(self._candidates) >= self.max_candidates:
                break
            asset_url = urljoin(base_url, path)
            self._add_candidate(
                asset_url,
                official_source_url,
                "common-asset",
                7,
                html_context=None,
                source_attribute="common-path",
                image_region="asset-path",
                provenance={
                    "source_page": official_source_url,
                    "source_domain": source_domain,
                    "discovery_method": "common-asset",
                    "fallback_level": 7,
                    "source_attribute": "common-path",
                    "image_region": "asset-path",
                    "official_page_reference": True,
                },
                evidence=["common official-domain asset path probe"],
            )

        return len(self._candidates) - initial_count

    def _discover_logo_fallback(self, official_source_url: str, source_domain: str) -> int:
        """Tier 8: Discover official logo via link rel=icon as final fallback."""
        if not source_domain:
            return 0

        initial_count = len(self._candidates)
        result = self._fetch_page_cached(official_source_url)
        if result.content is None:
            return len(self._candidates) - initial_count

        page_url = result.url or official_source_url
        soup = BeautifulSoup(result.content, "html.parser")
        icon_links = soup.find_all("link", rel=lambda x: x and "icon" in x)
        for link in icon_links:
            href = link.get("href")
            if not href:
                continue
            img_url = urljoin(page_url, href.strip())
            normalized_url = _normalize_candidate_url(img_url)
            if normalized_url in self._candidate_keys or len(self._candidates) >= self.max_candidates:
                continue
            rel_values = {str(value).lower() for value in (link.get("rel") or [])}
            is_apple_touch_icon = "apple-touch-icon" in rel_values
            source_attribute = "rel=apple-touch-icon" if is_apple_touch_icon else "rel=icon"
            evidence = (
                ["official page apple-touch-icon fallback"]
                if is_apple_touch_icon
                else ["official page icon fallback"]
            )
            self._add_candidate(
                img_url,
                page_url,
                "link-rel-icon",
                8,
                html_context=None,
                source_attribute=source_attribute,
                image_region="head",
                provenance={
                    "source_page": page_url,
                    "source_domain": source_domain,
                    "discovery_method": "link-rel-icon",
                    "fallback_level": 8,
                    "source_attribute": source_attribute,
                    "image_region": "head",
                    "official_page_reference": True,
                },
                evidence=evidence,
            )

        return len(self._candidates) - initial_count

    def _fetch_sitemap(self, sitemap_url: str, source_domain: str) -> list[str]:
        """Fetch sitemap.xml and extract URLs."""
        urls = []
        result = self._fetch_page_cached(sitemap_url)
        if result.content is None:
            return urls

        page_url = result.url or sitemap_url
        try:
            soup = BeautifulSoup(result.content, "html.parser")
            for loc in soup.find_all("loc"):
                url = loc.get_text(strip=True)
                if url.startswith("http"):
                    urls.append(urljoin(page_url, url))
        except Exception:
            pass

        return urls

    def _extract_subpage_links(self, result: PageFetchResult, page_url: str, source_domain: str, depth: int) -> list[str]:
        """Extract relevant same-domain subpage links for further crawling."""
        if depth >= MAX_CRAWL_DEPTH:
            return []

        soup = BeautifulSoup(result.content, "html.parser")

        relevant_keywords = (
            "scholarship", "scholarships", "program", "programme", "programmes",
            "study", "grant", "fund", "funding", "international", "exchange",
            "apply", "application", "about", "about-us", "news", "events",
            "pages", "course", "courses", "degree", "degrees", "masters",
            "phd", "research", "study-abroad", "admissions", "degree",
        )

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)
            if not parsed.scheme.startswith("http"):
                continue
            link_domain = parsed.netloc.lower()
            if link_domain != source_domain:
                continue

            link_path = parsed.path.lower()
            link_text = a.get_text(strip=True).lower()
            if not link_text and not link_path:
                continue

            if any(kw in link_path or kw in link_text for kw in relevant_keywords):
                links.append(full_url)

        return links[:5]

    def _fetch_page(self, url: str) -> PageFetchResult:
        tried_enhanced = False
        for attempt in range(self.max_retries + 1):
            try:
                headers = {"User-Agent": BROWSER_UA, "Accept": "text/html"}
                if tried_enhanced:
                    headers = {**headers, **ENHANCED_BROWSER_HEADERS}

                response = httpx.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                self._requests_made += 1
                final_url = getattr(response, "url", None)
                final_url = final_url if isinstance(final_url, str) else url
                if response.status_code != 200:
                    result = PageFetchResult(
                        url=final_url,
                        status_code=response.status_code,
                        content=None,
                        error=f"HTTP {response.status_code}",
                    )
                    self._record_request(result)
                    if response.status_code == 404:
                        result.error = "not_found"
                        return result
                    if response.status_code in TRANSIENT_STATUS_CODES and attempt < self.max_retries:
                        backoff = min(1.0 * (2 ** attempt), 8.0)
                        time.sleep(backoff)
                        continue
                    if response.status_code in TRANSIENT_BLOCKED_CODES and not tried_enhanced and attempt < self.max_retries:
                        tried_enhanced = True
                        backoff = min(1.0 * (2 ** attempt), 8.0)
                        time.sleep(backoff)
                        continue
                    if response.status_code in TRANSIENT_BLOCKED_CODES:
                        result.error = "temporarily_unavailable"
                    return result
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    return PageFetchResult(
                        url=final_url,
                        status_code=response.status_code,
                        content=None,
                        error=f"Non-HTML content-type: {content_type}",
                    )
                return PageFetchResult(url=final_url, status_code=response.status_code, content=response.text)
            except httpx.TimeoutException:
                self._timeout_count += 1
                self._requests_made += 1
                if attempt < self.max_retries:
                    backoff = min(1.0 * (2 ** attempt), 8.0)
                    time.sleep(backoff)
                    continue
                return PageFetchResult(url=url, status_code=None, content=None, error="timeout")
            except httpx.RequestError as exc:
                self._requests_made += 1
                if attempt < self.max_retries:
                    backoff = min(1.0 * (2 ** attempt), 8.0)
                    time.sleep(backoff)
                    continue
                return PageFetchResult(url=url, status_code=None, content=None, error=str(exc))
            except Exception as exc:
                self._requests_made += 1
                return PageFetchResult(url=url, status_code=None, content=None, error=str(exc))
        return PageFetchResult(url=url, status_code=None, content=None, error="max retries exceeded")

    def _extract_images(
        self,
        result: PageFetchResult,
        page_url: str,
        source_domain: str,
        fallback_level: int,
        include_fallback_level_8: bool = True,
        methods: set[str] | None = None,
    ) -> None:
        if not result.content:
            return

        enabled = methods or {
            "html-img", "picture-source", "link-image-src", "css-background",
            "og:image", "twitter:image", "json-ld", "link-rel-icon",
        }
        soup = BeautifulSoup(result.content, "html.parser")
        page_context = self._page_context(soup)

        if "og:image" in enabled or "twitter:image" in enabled:
            for attribute, method in (
                ("property", "og:image"),
                ("name", "twitter:image"),
            ):
                for meta in soup.find_all("meta"):
                    key = meta.get(attribute)
                    if key not in {
                        "og:image", "og:image:secure_url",
                        "twitter:image", "twitter:image:src",
                    }:
                        continue
                    content = meta.get("content")
                    if not content:
                        continue
                    img_url = urljoin(page_url, content.strip())
                    alt = meta.get("alt")
                    self._add_candidate(
                        img_url,
                        page_url,
                        method,
                        fallback_level,
                        alt_text=alt,
                        html_context=page_context,
                        source_attribute=key,
                        image_region="head",
                        provenance={
                            "source_page": page_url,
                            "source_domain": source_domain,
                            "discovery_method": method,
                            "fallback_level": fallback_level,
                            "source_attribute": key,
                            "image_region": "head",
                            "official_page_reference": True,
                        },
                        evidence=[f"official page metadata {key}"],
                    )

        if "json-ld" in enabled:
            for img_url, desc, schema_type in _extract_jsonld_images(soup, page_url):
                self._add_candidate(
                    img_url,
                    page_url,
                    "json-ld",
                    fallback_level,
                    html_context=page_context,
                    source_attribute="application/ld+json",
                    image_region="structured-data",
                    provenance={
                        "source_page": page_url,
                        "source_domain": source_domain,
                        "discovery_method": "json-ld",
                        "fallback_level": fallback_level,
                        "source_attribute": "application/ld+json",
                        "image_region": "structured-data",
                        "schema_type": schema_type,
                        "official_page_reference": True,
                    },
                    evidence=[f"JSON-LD {schema_type or 'image'} on official page"],
                )

        if "html-img" in enabled:
            for img in soup.find_all("img"):
                element_context = self._element_context(img, page_context)
                alt = img.get("alt")
                width = img.get("width")
                height = img.get("height")
                for source_attribute, img_url in self._iter_element_image_urls(img, page_url):
                    self._add_candidate(
                        img_url,
                        page_url,
                        "html-img",
                        fallback_level,
                        alt_text=alt,
                        width=width,
                        height=height,
                        html_context=element_context,
                        source_attribute=source_attribute,
                        image_region=self._element_region(img),
                        provenance={
                            "source_page": page_url,
                            "source_domain": source_domain,
                            "discovery_method": "html-img",
                            "fallback_level": fallback_level,
                            "source_attribute": source_attribute,
                            "image_region": self._element_region(img),
                            "official_page_reference": True,
                        },
                        evidence=[f"official page element referenced {source_attribute}"],
                    )

        if "picture-source" in enabled:
            for picture in soup.find_all("picture"):
                for source in picture.find_all("source"):
                    source_context = self._element_context(source, page_context)
                    for source_attribute, img_url in self._iter_element_image_urls(source, page_url):
                        self._add_candidate(
                            img_url,
                            page_url,
                            "picture-source",
                            fallback_level,
                            html_context=source_context,
                            source_attribute=source_attribute,
                            image_region=self._element_region(source),
                            provenance={
                                "source_page": page_url,
                                "source_domain": source_domain,
                                "discovery_method": "picture-source",
                                "fallback_level": fallback_level,
                                "source_attribute": source_attribute,
                                "image_region": self._element_region(source),
                                "official_page_reference": True,
                            },
                            evidence=[f"official picture source referenced {source_attribute}"],
                        )

        if "link-image-src" in enabled:
            for link in soup.find_all("link", rel=lambda value: value and "image_src" in value):
                href = link.get("href")
                if not href:
                    continue
                img_url = urljoin(page_url, href.strip())
                self._add_candidate(
                    img_url,
                    page_url,
                    "link-image-src",
                    fallback_level,
                    html_context=page_context,
                    source_attribute="rel=image_src",
                    image_region="head",
                    provenance={
                        "source_page": page_url,
                        "source_domain": source_domain,
                        "discovery_method": "link-image-src",
                        "fallback_level": fallback_level,
                        "source_attribute": "rel=image_src",
                        "image_region": "head",
                        "official_page_reference": True,
                    },
                    evidence=["official page link rel=image_src"],
                )

        if "css-background" in enabled:
            for img_url, source_attribute in self._extract_css_background_urls(soup, page_url):
                self._add_candidate(
                    img_url,
                    page_url,
                    "css-background",
                    fallback_level,
                    html_context=page_context,
                    source_attribute=source_attribute,
                    image_region="css-background",
                    provenance={
                        "source_page": page_url,
                        "source_domain": source_domain,
                        "discovery_method": "css-background",
                        "fallback_level": fallback_level,
                        "source_attribute": source_attribute,
                        "image_region": "css-background",
                        "official_page_reference": True,
                    },
                    evidence=["official page CSS background referenced the asset"],
                )

        if include_fallback_level_8 and "link-rel-icon" in enabled:
            for link in soup.find_all("link", rel=lambda value: value and "icon" in value):
                href = link.get("href")
                if not href:
                    continue
                img_url = urljoin(page_url, href.strip())
                rel_values = {str(value).lower() for value in (link.get("rel") or [])}
                is_apple_touch_icon = "apple-touch-icon" in rel_values
                source_attribute = "rel=apple-touch-icon" if is_apple_touch_icon else "rel=icon"
                evidence = (
                    ["official page apple-touch-icon fallback"]
                    if is_apple_touch_icon
                    else ["official page icon fallback"]
                )
                self._add_candidate(
                    img_url,
                    page_url,
                    "link-rel-icon",
                    8,
                    html_context=page_context,
                    source_attribute=source_attribute,
                    image_region="head",
                    provenance={
                        "source_page": page_url,
                        "source_domain": source_domain,
                        "discovery_method": "link-rel-icon",
                        "fallback_level": 8,
                        "source_attribute": source_attribute,
                        "image_region": "head",
                        "official_page_reference": True,
                    },
                    evidence=evidence,
                )

    def _page_context(self, soup: BeautifulSoup) -> str:
        title = soup.find("title")
        heading = soup.find(["h1", "h2"])
        description = soup.find("meta", attrs={"name": "description"})
        parts = []
        if title and title.get_text(strip=True):
            parts.append(title.get_text(strip=True))
        if heading and heading.get_text(strip=True):
            parts.append(heading.get_text(strip=True))
        if description and description.get("content"):
            parts.append(description.get("content"))
        return " | ".join(parts)[:500]

    @staticmethod
    def _element_region(element) -> str:
        if element.find_parent("picture"):
            return "picture"
        if element.find_parent("figure"):
            return "figure"
        if element.find_parent(["article", "main"]):
            return "content"
        if element.find_parent("nav"):
            return "navigation"
        if element.find_parent("header"):
            return "header"
        if element.find_parent("footer"):
            return "footer"
        if element.find_parent(["aside", "sidebar"]):
            return "sidebar"
        return "page"

    def _element_context(self, element, page_context: str) -> str:
        parent = element.find_parent(["figure", "article", "section", "main"])
        nearby = parent.get_text(" ", strip=True) if parent else ""
        if len(nearby) > 350:
            nearby = nearby[:350]
        return " | ".join(part for part in (page_context, nearby) if part)

    @staticmethod
    def _iter_element_image_urls(element, page_url: str):
        seen: set[str] = set()
        image_attributes = (
            "src",
            "data-src",
            "data-lazy-src",
            "data-original",
            "data-background",
            "data-bg",
            "data-image",
            "data-thumb",
            "background",
            "data-srcset",
            "data-lazy-srcset",
            "data-original-srcset",
            "srcset",
        )
        for attribute in image_attributes:
            value = element.get(attribute)
            if not value:
                continue
            if attribute.endswith("srcset"):
                urls = _extract_srcset_urls(value, page_url)
            else:
                if str(value).strip().startswith("data:"):
                    continue
                urls = [urljoin(page_url, str(value).strip())]
            for img_url in urls:
                if img_url not in seen:
                    seen.add(img_url)
                    yield attribute, img_url

    @staticmethod
    def _extract_css_background_urls(soup: BeautifulSoup, page_url: str):
        values: list[tuple[str, str]] = []
        for element in soup.find_all(attrs={"style": True}):
            values.append((element.get("style", ""), "style"))
        for style in soup.find_all("style"):
            values.append((style.get_text(), "style-tag"))
        css_url_pattern = re.compile(
            r"url\(\s*(?:(['\"])(.*?)\1|([^'\"()]*?))\s*\)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        for value, source_attribute in values:
            for match in css_url_pattern.finditer(value):
                raw_url = (match.group(2) if match.group(1) else match.group(3)).strip().strip("\"'")
                if not raw_url or raw_url.startswith(("data:", "javascript:")):
                    continue
                yield urljoin(page_url, raw_url), source_attribute

    def _add_candidate(
        self,
        image_url: str,
        page_url: str,
        discovery_method: str,
        fallback_level: int,
        alt_text: str | None = None,
        width: str | int | None = None,
        height: str | int | None = None,
        html_context: str | None = None,
        source_attribute: str | None = None,
        image_region: str | None = None,
        provenance: dict | None = None,
        evidence: list[str] | None = None,
    ) -> None:
        parsed = urlparse(image_url)
        if parsed.scheme.lower() not in {"http", "https"}:
            return None

        normalized_url = _normalize_candidate_url(image_url)

        if not normalized_url:
            return

        existing = next((candidate for candidate in self._candidates if candidate.normalized_url == normalized_url), None)
        if existing:
            self._merge_candidate(
                existing,
                discovery_method,
                fallback_level,
                alt_text,
                width,
                height,
                source_attribute,
                image_region,
                provenance,
                evidence,
            )
            return

        if len(self._candidates) >= self.max_candidates:
            return

        candidate_evidence = list(evidence or [])
        candidate_provenance = dict(provenance or {})
        candidate_provenance.setdefault("source_page", page_url)
        candidate_provenance.setdefault("source_domain", _extract_netloc(page_url))
        candidate_provenance.setdefault("discovery_method", discovery_method)
        candidate_provenance.setdefault("discovery_methods", [discovery_method])
        candidate_provenance.setdefault("fallback_level", fallback_level)
        candidate_provenance.setdefault("official_page_reference", True)

        candidate = ImageCandidate(
            image_url=image_url,
            page_url=page_url,
            discovery_method=discovery_method,
            fallback_level=fallback_level,
            alt_text=alt_text,
            width=_to_int(width),
            height=_to_int(height),
            html_context=html_context,
            normalized_url=normalized_url,
            discovery_methods=[discovery_method],
            source_attribute=source_attribute,
            image_region=image_region,
            provenance=candidate_provenance,
            evidence=candidate_evidence,
        )
        self._candidates.append(candidate)
        self._candidate_keys.add(normalized_url)

    def _merge_candidate(
        self,
        candidate: ImageCandidate,
        discovery_method: str,
        fallback_level: int,
        alt_text: str | None,
        width: str | int | None,
        height: str | int | None,
        source_attribute: str | None,
        image_region: str | None,
        provenance: dict | None,
        evidence: list[str] | None,
    ) -> None:
        if discovery_method not in candidate.discovery_methods:
            candidate.discovery_methods.append(discovery_method)
        if _DISCOVERY_METHOD_PRIORITY.get(discovery_method, 99) < _DISCOVERY_METHOD_PRIORITY.get(candidate.discovery_method, 99):
            candidate.discovery_method = discovery_method
        previous_fallback_level = candidate.fallback_level
        candidate.fallback_level = min(candidate.fallback_level, fallback_level)
        if alt_text and not candidate.alt_text:
            candidate.alt_text = alt_text
        if width and not candidate.width:
            candidate.width = _to_int(width)
        if height and not candidate.height:
            candidate.height = _to_int(height)
        if source_attribute:
            candidate.source_attribute = source_attribute
        if image_region:
            candidate.image_region = image_region

        incoming_page = provenance.get("source_page") if provenance else None
        current_page = candidate.provenance.get("source_page", candidate.page_url)
        incoming_normalized = _normalize_candidate_url(str(incoming_page)) if incoming_page else None
        current_normalized = _normalize_candidate_url(str(current_page)) if current_page else None
        canonical_urls = {
            _normalize_candidate_url(url)
            for url in self._canonical_page_urls
            if _normalize_candidate_url(url)
        }
        incoming_is_canonical = incoming_normalized in canonical_urls
        current_is_canonical = current_normalized in canonical_urls
        replace_source_page = (
            (incoming_is_canonical and not current_is_canonical)
            or (not incoming_is_canonical and not current_is_canonical and fallback_level < previous_fallback_level)
        )

        if provenance:
            existing_methods = list(
                dict.fromkeys(
                    candidate.provenance.get(
                        "discovery_methods", candidate.discovery_methods
                    )
                    + [discovery_method]
                )
            )
            candidate.provenance.update(provenance)
            selected_source_page = (
                str(incoming_page)
                if replace_source_page and incoming_page
                else current_page
            )
            candidate.provenance["source_page"] = selected_source_page
            candidate.provenance["source_domain"] = provenance.get(
                "source_domain",
                _extract_netloc(selected_source_page),
            )
            candidate.provenance["discovery_method"] = candidate.discovery_method
            candidate.provenance["fallback_level"] = candidate.fallback_level
            candidate.provenance["discovery_methods"] = existing_methods
            if replace_source_page:
                candidate.page_url = selected_source_page
        candidate.evidence.extend(item for item in (evidence or []) if item not in candidate.evidence)

    def fetch_page(self, url: str) -> PageFetchResult:
        """Public method for external callers needing page content."""
        return self._fetch_page(url)

    def extract_images_from_html(self, content: str, page_url: str, depth: int = 0) -> list[ImageCandidate]:
        """Public method to extract images from pre-fetched HTML content."""
        self._candidates.clear()
        result = PageFetchResult(url=page_url, status_code=200, content=content)
        self._extract_images(result, page_url, _extract_netloc(page_url), 1)
        return self._candidates


def _extract_netloc(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.netloc.lower() if parsed.netloc else None


def _is_page_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if not path or path.endswith("/"):
        return True
    non_page_extensions = {
        ".avif", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp",
        ".css", ".js", ".json", ".xml", ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".zip", ".gz", ".tar", ".rar", ".mp3", ".mp4", ".webm", ".wav",
    }
    return not any(path.endswith(extension) for extension in non_page_extensions)


def _normalize_candidate_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None

    hostname = parsed.hostname
    if not hostname:
        return None
    try:
        hostname = hostname.lower()
    except (TypeError, ValueError):
        return None

    try:
        port = parsed.port
    except ValueError:
        return None
    default_port = (parsed.scheme.lower() == "http" and port == 80) or (
        parsed.scheme.lower() == "https" and port == 443
    )
    netloc = hostname
    if port is not None and not default_port:
        netloc = f"{hostname}:{port}"

    path = re.sub(
        r"%([0-9a-fA-F]{2})",
        lambda match: "%" + match.group(1).upper(),
        parsed.path or "/",
    )
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_PARAMETERS
    ]
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def _to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_srcset_urls(value: str, page_url: str) -> list[str]:
    urls: list[str] = []
    for candidate in re.split(r"\s*,\s*", value.strip()):
        if not candidate:
            continue
        raw_url = candidate.split()[0].strip().strip("\"'")
        if not raw_url or raw_url.startswith(("data:", "javascript:")):
            continue
        img_url = urljoin(page_url, raw_url)
        if img_url not in urls:
            urls.append(img_url)
    return urls


def _extract_jsonld_images(soup: BeautifulSoup, page_url: str) -> list[JsonLdImageReference]:
    results: list[JsonLdImageReference] = []
    seen: set[str] = set()
    image_types = {"ImageObject", "MediaObject", "VisualArtwork", "Photograph"}

    def add_image(value: object, fallback_type: str | None, description: str | None = None) -> None:
        if isinstance(value, str) and value.strip():
            img_url = urljoin(page_url, value.strip())
        elif isinstance(value, dict):
            img_url_value = value.get("url")
            if not isinstance(img_url_value, str) or not img_url_value.strip():
                return
            img_url = urljoin(page_url, img_url_value.strip())
            description = value.get("name") or value.get("description") or description
            fallback_type = value.get("@type") or fallback_type
        else:
            return

        if img_url in seen:
            return
        seen.add(img_url)
        results.append((img_url, description, fallback_type))

    def _normalize_type(value: object) -> str | None:
        """JSON-LD @type may be a str, a list of str, or absent; normalize to a single str."""
        if isinstance(value, str):
            return value or None
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    return item
            return None
        return None

    def walk(value: object, inherited_type: str | None = None) -> None:
        if isinstance(value, dict):
            node_type = _normalize_type(value.get("@type")) or inherited_type
            for key in ("image", "logo", "photo"):
                child = value.get(key)
                if isinstance(child, dict):
                    add_image(child, node_type, value.get("name") or value.get("description"))
                    walk(child, node_type)
                else:
                    add_image(child, node_type, value.get("name") or value.get("description"))
            if node_type in image_types:
                add_image(value.get("url"), node_type, value.get("name") or value.get("description"))
            for key, child in value.items():
                if key not in {"image", "logo", "photo", "url"}:
                    walk(child, node_type)
        elif isinstance(value, list):
            for child in value:
                walk(child, inherited_type)

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        import json
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, ValueError):
            continue
        walk(data if isinstance(data, list) else [data])
    return results


def _extract_link_icons(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Extract link rel=icon URLs for logo fallback (tier 8)."""
    results = []
    for link in soup.find_all("link", rel=lambda x: x and "icon" in x):
        href = link.get("href")
        if not href:
            continue
        img_url = urljoin(page_url, href.strip())
        results.append(img_url)
    return results
