"""Evidence-driven image discovery from official scholarship source URLs.

Discovers candidate image URLs by scraping the scholarship's
official_source_url and following same-domain links to relevant
sub-pages (program pages, application pages, etc.).

Designed for read-only dry-run validation — never writes to the database.
"""

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
MAX_PAGES_PER_SOURCE = 10
MAX_CANDIDATES = 50


@dataclass
class ImageCandidate:
    image_url: str
    page_url: str
    discovery_method: str
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

    def __init__(self, timeout: float = 30.0, max_candidates: int = MAX_CANDIDATES):
        self.timeout = timeout
        self.max_candidates = max_candidates
        self._seen_pages: set[str] = set()
        self._candidates: list[ImageCandidate] = []

    def discover_from_scholarship(self, official_source_url: str) -> list[ImageCandidate]:
        """Start discovery from a scholarship's canonical official_source_url."""
        self._seen_pages.clear()
        self._candidates.clear()

        if not official_source_url:
            return []

        self._crawl_page(official_source_url, depth=0)

        for i in range(len(self._candidates)):
            if len(self._candidates) >= self.max_candidates:
                break

        return self._candidates[: self.max_candidates]

    def _crawl_page(self, url: str, depth: int) -> None:
        if url in self._seen_pages:
            return
        if len(self._seen_pages) >= MAX_PAGES_PER_SOURCE:
            return
        if depth > MAX_CRAWL_DEPTH:
            return

        page_domain = _extract_netloc(url)
        source_domain = _extract_netloc(url)
        if not page_domain or not is_official_domain(page_domain):
            return

        self._seen_pages.add(url)
        result = self._fetch_page(url)
        if result.content is None:
            return

        subpage_urls = self._extract_subpage_links(result, url, source_domain, depth)
        self._extract_images(result, url, source_domain, depth)

        for sub_url in subpage_urls:
            if len(self._seen_pages) >= MAX_PAGES_PER_SOURCE:
                break
            self._crawl_page(sub_url, depth + 1)

    def _extract_subpage_links(self, result: PageFetchResult, page_url: str, source_domain: str, depth: int) -> list[str]:
        """Extract relevant same-domain subpage links for further crawling."""
        if depth >= MAX_CRAWL_DEPTH:
            return []

        soup = BeautifulSoup(result.content, "html.parser")

        relevant_keywords = ("scholarship", "scholarships", "program", "programme",
                             "study", "grant", "fund", "international", "exchange")

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
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": BROWSER_UA, "Accept": "text/html"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            if response.status_code != 200:
                return PageFetchResult(url=url, status_code=response.status_code, content=None, error=f"HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return PageFetchResult(url=url, status_code=response.status_code, content=None, error=f"Non-HTML content-type: {content_type}")
            return PageFetchResult(url=url, status_code=response.status_code, content=response.text)
        except httpx.RequestError as exc:
            return PageFetchResult(url=url, status_code=None, content=None, error=str(exc))
        except Exception as exc:
            return PageFetchResult(url=url, status_code=None, content=None, error=str(exc))

    def _extract_images(self, result: PageFetchResult, page_url: str, source_domain: str, depth: int) -> None:
        if not result.content:
            return

        soup = BeautifulSoup(result.content, "html.parser")

        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            img_url = urljoin(page_url, og_image["content"].strip())
            self._add_candidate(img_url, page_url, "og:image", soup, depth)

        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            img_url = urljoin(page_url, twitter_image["content"].strip())
            self._add_candidate(img_url, page_url, "twitter:image", soup, depth)

        json_ld_images = _extract_jsonld_images(soup, page_url)
        for img_url, desc in json_ld_images:
            self._add_candidate(img_url, page_url, "json-ld", soup, depth)

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src:
                continue
            if src.startswith("data:"):
                continue
            img_url = urljoin(page_url, src.strip())
            alt = img.get("alt")
            width = img.get("width")
            height = img.get("height")
            self._add_candidate(
                img_url, page_url, "html-img", soup, depth,
                alt_text=alt, width=width, height=height,
            )

    def _add_candidate(
        self,
        image_url: str,
        page_url: str,
        discovery_method: str,
        soup: BeautifulSoup,
        depth: int,
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
        self._extract_images(result, page_url, _extract_netloc(page_url), depth)
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
            if isinstance(item, dict):
                for key in ("image", "logo", "photo"):
                    val = item.get(key)
                    if isinstance(val, str) and val:
                        img_url = urljoin(page_url, val.strip())
                        results.append((img_url, item.get("name") or item.get("description")))
                    elif isinstance(val, list):
                        for sub in val:
                            if isinstance(sub, str) and sub:
                                img_url = urljoin(page_url, sub.strip())
                                results.append((img_url, None))
    return results
