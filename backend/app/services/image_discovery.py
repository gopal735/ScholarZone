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

import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..services.scholarship_image_verifier import ImageSourceType, is_official_domain


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

MAX_CRAWL_DEPTH = 2
MAX_PAGES_PER_SOURCE = 25
MAX_CANDIDATES = 50
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
        self._start_time: float = 0.0
        self._requests_made: int = 0
        self._timeout_count: int = 0
        self._blocked_count: int = 0
        self._transient_error_count: int = 0

    def discover_from_scholarship(self, official_source_url: str) -> list[ImageCandidate]:
        """Start discovery from a scholarship's canonical official_source_url.

        Exhausts all discovery tiers before returning.
        """
        self._seen_pages.clear()
        self._candidates.clear()
        self._start_time = time.time()
        self._requests_made = 0
        self._timeout_count = 0
        self._blocked_count = 0
        self._transient_error_count = 0

        if not official_source_url:
            return []

        source_domain = _extract_netloc(official_source_url)

        # Tier 1: Canonical official_source_url
        self._crawl_page(official_source_url, depth=0, fallback_level=1, source_domain=source_domain)

        # Tier 2: Relevant official scholarship/program pages on same domain
        if len(self._candidates) < self.max_candidates and not self._is_timed_out():
            self._discover_same_domain_program_pages(official_source_url, source_domain)

        # Tier 3: Official provider/government/university pages on known official domains
        if len(self._candidates) < self.max_candidates and not self._is_timed_out():
            self._discover_cross_domain_official_pages(official_source_url, source_domain)

        # Tier 7: Official domain asset paths
        if len(self._candidates) < self.max_candidates and not self._is_timed_out():
            self._probe_common_asset_paths(official_source_url, source_domain)

        # Tier 8: Official logo as FINAL FALLBACK
        if len(self._candidates) < self.max_candidates and not self._is_timed_out():
            self._discover_logo_fallback(official_source_url, source_domain)

        return self._candidates[: self.max_candidates]

    def discover_tier_by_tier(self, official_source_url: str):
        """Yield (tier_name, candidates_added) tuples for each discovery tier.

        Allows caller to validate after each tier and stop early when
        HIGH-confidence PROGRAM_IMAGE or strong OFFICIAL_BANNER is found.
        """
        self._seen_pages.clear()
        self._candidates.clear()
        self._start_time = time.time()
        self._requests_made = 0
        self._timeout_count = 0
        self._blocked_count = 0
        self._transient_error_count = 0

        if not official_source_url:
            return

        source_domain = _extract_netloc(official_source_url)

        # Tier 1: Canonical official_source_url
        added = self._crawl_page(official_source_url, depth=0, fallback_level=1, source_domain=source_domain)
        yield "tier1_canonical", added

        if self._is_timed_out():
            return

        # Tier 2: Same-domain program pages
        added = self._discover_same_domain_program_pages(official_source_url, source_domain)
        yield "tier2_same_domain", added

        if self._is_timed_out():
            return

        # Tier 3: Cross-domain official pages
        added = self._discover_cross_domain_official_pages(official_source_url, source_domain)
        yield "tier3_cross_domain", added

        if self._is_timed_out():
            return

        # Tier 4+5+6 happen inside _crawl_page and _extract_images

        # Tier 7: Common asset paths
        added = self._probe_common_asset_paths(official_source_url, source_domain)
        yield "tier7_common_assets", added

        if self._is_timed_out():
            return

        # Tier 8: Logo fallback
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

    def _crawl_page(self, url: str, depth: int, fallback_level: int, source_domain: str) -> int:
        if url in self._seen_pages:
            return 0
        if len(self._seen_pages) >= MAX_PAGES_PER_SOURCE:
            return 0
        if depth > MAX_CRAWL_DEPTH:
            return 0

        page_domain = _extract_netloc(url)
        if not page_domain or not is_official_domain(page_domain):
            return 0

        self._seen_pages.add(url)
        result = self._fetch_page(url)
        if result.content is None:
            return 0

        initial_count = len(self._candidates)

        # Tier 4 + 5 + 6: HTML image assets, OG metadata, structured data
        self._extract_images(result, url, source_domain, fallback_level, include_fallback_level_8=False)

        # Tier 2: Subpage links on same domain
        if fallback_level <= 2:
            subpage_urls = self._extract_subpage_links(result, url, source_domain, depth)
            for sub_url in subpage_urls:
                if len(self._seen_pages) >= MAX_PAGES_PER_SOURCE:
                    break
                if self._is_timed_out():
                    break
                self._crawl_page(sub_url, depth + 1, fallback_level=2, source_domain=source_domain)

        return len(self._candidates) - initial_count

    def _discover_same_domain_program_pages(self, official_source_url: str, source_domain: str) -> int:
        """Tier 2: Discover program pages on the same domain via sitemap and common paths."""
        if not source_domain:
            return 0

        parsed = urlparse(official_source_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        initial_count = len(self._candidates)

        # Try sitemap.xml
        sitemap_urls = self._fetch_sitemap(f"{base_url}/sitemap.xml", source_domain)
        for sitemap_url in sitemap_urls[:5]:
            if sitemap_url not in self._seen_pages and len(self._seen_pages) < MAX_PAGES_PER_SOURCE:
                if self._is_timed_out():
                    break
                self._crawl_page(sitemap_url, depth=0, fallback_level=2, source_domain=source_domain)

        # Try common program paths
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
            if page_url not in self._seen_pages and len(self._seen_pages) < MAX_PAGES_PER_SOURCE:
                self._crawl_page(page_url, depth=0, fallback_level=2, source_domain=source_domain)

        return len(self._candidates) - initial_count

    def _discover_cross_domain_official_pages(self, official_source_url: str, source_domain: str) -> int:
        """Tier 3: Follow links to known official domains (government, university, provider)."""
        if not official_source_url:
            return 0

        initial_count = len(self._candidates)
        result = self._fetch_page(official_source_url)
        if result.content is None:
            return len(self._candidates) - initial_count

        soup = BeautifulSoup(result.content, "html.parser")
        known_official_suffixes = [
            ".gov", ".go.kr", ".go.jp", ".ac.kr", ".ac.jp", ".ac.cn",
            ".edu", ".europa.eu", "erasmus-plus.ec.europa.eu",
            "daad.de", "iccr.gov.in", "studyinkorea.go.kr", "studyinjapan.go.jp",
            "campusfrance.org", "fulbrightonline.org", "educationusa.state.gov",
            "aefe.gouv.fr", "gouv.fr", "a-star.edu.sg", "nuffic.nl", "si.se",
            "esteri.it", "ec.europa.eu",
        ]

        cross_domain_urls = []
        for a in soup.find_all("a", href=True):
            if self._is_timed_out():
                break
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full_url = urljoin(official_source_url, href)
            parsed = urlparse(full_url)
            if not parsed.scheme.startswith("http"):
                continue
            link_domain = parsed.netloc.lower()
            if link_domain == source_domain:
                continue
            if any(link_domain == suffix or link_domain.endswith(f".{suffix}") or suffix in link_domain
                   for suffix in known_official_suffixes):
                cross_domain_urls.append(full_url)

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
            "/logo.png", "/logo.svg", "/logo.jpg", "/logo.gif", "/logo.webp",
            "/images/logo.png", "/images/logo.svg", "/images/logo.jpg",
            "/assets/logo.png", "/assets/logo.svg", "/assets/logo.jpg",
            "/img/logo.png", "/img/logo.jpg",
            "/banner.png", "/banner.jpg", "/banner.svg", "/banner.webp",
            "/images/banner.png", "/images/banner.jpg",
            "/header.jpg", "/header.png",
            "/hero.jpg", "/hero.png",
            "/homepage-banner.jpg", "/homepage-banner.png",
            "/images/header.jpg", "/images/header.png",
            "/images/hero.jpg", "/images/hero.png",
        ]

        for path in common_paths:
            if len(self._candidates) >= self.max_candidates:
                break
            asset_url = urljoin(base_url, path)
            if asset_url not in {c.image_url for c in self._candidates}:
                self._add_candidate(asset_url, official_source_url, "common-asset", None, 7)

        return len(self._candidates) - initial_count

    def _discover_logo_fallback(self, official_source_url: str, source_domain: str) -> int:
        """Tier 8: Discover official logo via link rel=icon as final fallback."""
        if not source_domain:
            return 0

        initial_count = len(self._candidates)
        result = self._fetch_page(official_source_url)
        if result.content is None:
            return len(self._candidates) - initial_count

        soup = BeautifulSoup(result.content, "html.parser")
        icon_links = soup.find_all("link", rel=lambda x: x and "icon" in x)
        for link in icon_links:
            href = link.get("href")
            if not href:
                continue
            img_url = urljoin(official_source_url, href.strip())
            if img_url not in {c.image_url for c in self._candidates} and len(self._candidates) < self.max_candidates:
                self._add_candidate(img_url, official_source_url, "link-rel-icon", soup, 8)

        return len(self._candidates) - initial_count

    def _fetch_sitemap(self, sitemap_url: str, source_domain: str) -> list[str]:
        """Fetch sitemap.xml and extract URLs."""
        urls = []
        result = self._fetch_page(sitemap_url)
        if result.content is None:
            return urls

        try:
            soup = BeautifulSoup(result.content, "html.parser")
            for loc in soup.find_all("loc"):
                url = loc.get_text(strip=True)
                if url.startswith("http"):
                    urls.append(url)
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
                if response.status_code != 200:
                    result = PageFetchResult(
                        url=url,
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
                        url=url,
                        status_code=response.status_code,
                        content=None,
                        error=f"Non-HTML content-type: {content_type}",
                    )
                return PageFetchResult(url=url, status_code=response.status_code, content=response.text)
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

    def _extract_images(self, result: PageFetchResult, page_url: str, source_domain: str, fallback_level: int, include_fallback_level_8: bool = True) -> None:
        if not result.content:
            return

        soup = BeautifulSoup(result.content, "html.parser")

        # Tier 5: Open Graph / social preview metadata
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            img_url = urljoin(page_url, og_image["content"].strip())
            self._add_candidate(img_url, page_url, "og:image", soup, fallback_level)

        og_image_secure = soup.find("meta", attrs={"property": "og:image:secure_url"})
        if og_image_secure and og_image_secure.get("content"):
            img_url = urljoin(page_url, og_image_secure["content"].strip())
            self._add_candidate(img_url, page_url, "og:image", soup, fallback_level)

        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            img_url = urljoin(page_url, twitter_image["content"].strip())
            self._add_candidate(img_url, page_url, "twitter:image", soup, fallback_level)

        twitter_image_src = soup.find("meta", attrs={"name": "twitter:image:src"})
        if twitter_image_src and twitter_image_src.get("content"):
            img_url = urljoin(page_url, twitter_image_src["content"].strip())
            self._add_candidate(img_url, page_url, "twitter:image", soup, fallback_level)

        # Tier 6: Structured metadata (JSON-LD)
        json_ld_images = _extract_jsonld_images(soup, page_url)
        for img_url, desc in json_ld_images:
            self._add_candidate(img_url, page_url, "json-ld", soup, fallback_level)

        # Tier 4: HTML image assets
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-srcset")
            if not src:
                continue
            if src.startswith("data:"):
                continue
            # Handle srcset (take first URL)
            if "srcset" in img.attrs and not src.startswith("http"):
                srcset = img.get("srcset", "")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
            img_url = urljoin(page_url, src.strip())
            alt = img.get("alt")
            width = img.get("width")
            height = img.get("height")
            self._add_candidate(
                img_url, page_url, "html-img", soup, fallback_level,
                alt_text=alt, width=width, height=height,
            )

        # <picture><source> tags
        for picture in soup.find_all("picture"):
            for source in picture.find_all("source"):
                srcset = source.get("srcset") or source.get("data-srcset")
                if srcset:
                    first_src = srcset.split(",")[0].strip().split(" ")[0]
                    img_url = urljoin(page_url, first_src)
                    self._add_candidate(img_url, page_url, "html-img", soup, fallback_level)

        # link[rel="image_src"]
        image_src = soup.find("link", rel=lambda x: x and "image_src" in x)
        if image_src and image_src.get("href"):
            img_url = urljoin(page_url, image_src["href"].strip())
            self._add_candidate(img_url, page_url, "link-image-src", soup, fallback_level)

        # Tier 8: Official logo as FINAL FALLBACK via link rel=icon
        if include_fallback_level_8:
            link_icons = _extract_link_icons(soup, page_url)
            for img_url in link_icons:
                self._add_candidate(img_url, page_url, "link-rel-icon", soup, 8)

    def _add_candidate(
        self,
        image_url: str,
        page_url: str,
        discovery_method: str,
        soup: BeautifulSoup,
        fallback_level: int,
        alt_text: str | None = None,
        width: str | int | None = None,
        height: str | int | None = None,
    ) -> None:
        parsed = urlparse(image_url)
        if not parsed.scheme.startswith("http"):
            return

        if image_url in {c.image_url for c in self._candidates}:
            return

        if len(self._candidates) >= self.max_candidates:
            return

        html_context = None
        if soup:
            parent_text = None
            if soup.find("title"):
                parent_text = soup.find("title").get_text(strip=True)
            if parent_text:
                html_context = parent_text[:200]

        candidate = ImageCandidate(
            image_url=image_url,
            page_url=page_url,
            discovery_method=discovery_method,
            fallback_level=fallback_level,
            alt_text=alt_text,
            width=_to_int(width),
            height=_to_int(height),
            html_context=html_context,
        )
        self._candidates.append(candidate)

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


def _to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_jsonld_images(soup: BeautifulSoup, page_url: str) -> list[tuple[str, str | None]]:
    results = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        import json
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            # Check top-level keys for image/logo/photo/url
            for key in ("image", "logo", "photo", "url"):
                val = item.get(key)
                if isinstance(val, str) and val:
                    img_url = urljoin(page_url, val.strip())
                    results.append((img_url, item.get("name") or item.get("description")))
                elif isinstance(val, list):
                    for sub in val:
                        if isinstance(sub, str) and sub:
                            img_url = urljoin(page_url, sub.strip())
                            results.append((img_url, None))

            # Recurse into nested dicts and lists
            for v in item.values():
                if isinstance(v, dict):
                    for key in ("image", "logo", "photo", "url"):
                        val = v.get(key)
                        if isinstance(val, str) and val:
                            img_url = urljoin(page_url, val.strip())
                            results.append((img_url, v.get("name") or v.get("description")))
                        elif isinstance(val, list):
                            for sub in val:
                                if isinstance(sub, str) and sub:
                                    img_url = urljoin(page_url, sub.strip())
                                    results.append((img_url, None))
                elif isinstance(v, list):
                    for sub in v:
                        if isinstance(sub, dict):
                            for key in ("image", "logo", "photo", "url"):
                                val = sub.get(key)
                                if isinstance(val, str) and val:
                                    img_url = urljoin(page_url, val.strip())
                                    results.append((img_url, sub.get("name") or sub.get("description")))
                                elif isinstance(val, list):
                                    for ssub in val:
                                        if isinstance(ssub, str) and ssub:
                                            img_url = urljoin(page_url, ssub.strip())
                                            results.append((img_url, None))
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
