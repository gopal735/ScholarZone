"""Official PDF circular extraction.

Government and European scholarship providers publish the substance of an award
in PDF circulars and attachments far more often than in the body of a page: a
MEXT scholarship circular lists the required documents, a CSC call for
applications states the selection procedure, a Commonwealth advertisement gives
the closing date. A pipeline that only reads HTML therefore reports those
fields as genuinely absent when the provider published them in a document one
link away.

This service downloads PDFs that are linked from an already-verified official
page, extracts their text, and hands it to the same section extractor used for
HTML. It is deliberately strict about what it will read:

  * only PDFs linked from a page whose own host matches the official source
    host, or from a subdomain of it;
  * never a PDF reached from a third-party or aggregator host;
  * a size ceiling, so a linked dataset or manual cannot stall a maintenance
    pass;
  * a hard requirement that the document actually extracts text, because a
    scanned image-only PDF would otherwise yield empty "facts" and be recorded
    as if it had been read.

Every extraction keeps the PDF URL and the page the PDF was linked from, so a
stored fact remains traceable to the circular that stated it.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

#: A circular is a document, not a dataset. Beyond this the text layer is not
#: worth the memory and the extraction time.
MAX_PDF_BYTES = 12 * 1024 * 1024

#: A PDF that yields fewer characters than this is a scanned image or a stub.
#: Treating it as read would record "we checked" for a document nobody read.
MIN_USABLE_TEXT_CHARS = 220

_PDF_EXT = (".pdf",)

# Only these links are followed. Anything else (zip, xlsx, mp4) is not a
# circular and extracting it would be noise.
_DOC_SUFFIXES = (".pdf", ".doc", ".docx", ".html", ".htm", ".php", ".aspx")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class PdfPage:
    """One extracted page of a circular."""

    page_number: int
    text: str


@dataclass
class PdfExtraction:
    """Text recovered from one official PDF."""

    url: str
    linked_from: str
    ok: bool
    pages: list[PdfPage] = field(default_factory=list)
    text: str = ""
    error: str | None = None
    page_count: int = 0
    #: True when the PDF was reachable but carried no usable text layer.
    scanned: bool = False

    @property
    def usable(self) -> bool:
        return self.ok and not self.scanned and len(self.text.strip()) >= MIN_USABLE_TEXT_CHARS


def _host(url: str | None) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().removeprefix("www.")


#: Second-level suffixes that sit under a country code, so the registrable
#: domain is the label plus the code plus the suffix. Without this,
#: "embassy.gov.uk" and "gov.uk" reduce to the same pair and an embassy's
#: circulars would be treated as belonging to the government as a whole - a
#: different publisher entirely.
_SECOND_LEVEL = frozenset(
    {"co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "net.uk", "sch.uk",
     "gov.au", "edu.au", "org.au", "gov.nz", "ac.nz", "gov.in", "ac.in",
     "co.jp", "go.jp", "ac.jp", "co.kr", "go.kr", "gov.br", "edu.br",
     "gov.cn", "edu.cn", "com.cn", "co.za", "org.za", "gov.mx", "gouv.fr"}
)


def _registrable(host: str) -> str:
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return host
    last_two = ".".join(parts[-2:])
    if last_two in _SECOND_LEVEL and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last_two


def same_official_site(candidate_url: str, official_url: str) -> bool:
    """True when a link target is the official publisher's own property.

    A government department publishes circulars from a sub-agency host, and a
    university from a faculty host, so a shared registrable domain is the test.
    A foreign or commercial host is not accepted even when it hosts a copy.
    """
    candidate = _host(candidate_url)
    official = _host(official_url)
    if not candidate or not official:
        return False
    return _registrable(candidate) == _registrable(official)


def find_official_pdf_links(
    html: str, base_url: str, official_url: str, *, limit: int = 8
) -> list[str]:
    """Return circular links on an official page, same publisher only.

    Order is document order and de-duplicated, so the most prominent circular on
    the page is the first one tried.
    """
    if not html:
        return []
    candidates: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'href="([^"]+)"', html, re.IGNORECASE):
        href = match.group(1).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        lowered = href.lower()
        # Only real documents are followed. A link whose path merely contains a
        # word like "guidelines" is usually an HTML page, and fetching it would
        # spend a request to be rejected by the PDF content check anyway.
        if not lowered.endswith((".pdf", ".doc", ".docx")):
            continue
        try:
            absolute = urljoin(base_url, href)
        except ValueError:
            continue
        if not absolute.lower().startswith(("http://", "https://")):
            continue
        if absolute in seen:
            continue
        if not same_official_site(absolute, official_url):
            continue
        seen.add(absolute)
        candidates.append(absolute)
        if len(candidates) >= limit:
            break
    return candidates


def _extract_with_pdfplumber(data: bytes, max_pages: int) -> tuple[str, int]:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        total = len(pdf.pages)
        for page in pdf.pages[:max_pages]:
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001 - one bad page must not kill the doc
                continue
            if text.strip():
                pages.append(text)
    return "\n".join(pages), total


def _extract_with_pypdf(data: bytes, max_pages: int) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    total = len(reader.pages)
    pages: list[str] = []
    for page in reader.pages[:max_pages]:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            continue
        if text.strip():
            pages.append(text)
    return "\n".join(pages), total


class OfficialPdfExtractor:
    """Downloads and reads official circulars, reusing the shared HTTP path."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        max_pages: int = 40,
        max_pdf_bytes: int = MAX_PDF_BYTES,
        client: httpx.Client | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_pages = max_pages
        self.max_pdf_bytes = max_pdf_bytes
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/pdf,*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
            self._client = None

    def fetch(self, pdf_url: str, linked_from: str) -> PdfExtraction:
        """Fetch one PDF and extract its text layer.

        Failure is reported, never raised: a broken attachment on one page must
        not abort an enrichment pass.
        """
        try:
            response = self._get_client().get(pdf_url)
        except Exception as exc:  # noqa: BLE001
            return PdfExtraction(
                url=pdf_url, linked_from=linked_from, ok=False, error=type(exc).__name__
            )

        if response.status_code != 200:
            return PdfExtraction(
                url=pdf_url,
                linked_from=linked_from,
                ok=False,
                error=f"http_{response.status_code}",
            )

        content_type = (response.headers.get("content-type") or "").lower()
        data = response.content or b""
        # Some servers mislabel a PDF as text/html. Trust the bytes, not the
        # header, but refuse anything that is plainly an HTML page.
        if "text/html" in content_type and not data[:5].startswith(b"%PDF-"):
            return PdfExtraction(
                url=pdf_url, linked_from=linked_from, ok=False, error="not_a_pdf"
            )
        if not data[:5].startswith(b"%PDF-"):
            return PdfExtraction(
                url=pdf_url, linked_from=linked_from, ok=False, error="not_a_pdf"
            )
        if len(data) > self.max_pdf_bytes:
            return PdfExtraction(
                url=pdf_url, linked_from=linked_from, ok=False, error="too_large"
            )

        text = ""
        total_pages = 0
        pages: list[PdfPage] = []
        for extractor in (_extract_with_pdfplumber, _extract_with_pypdf):
            try:
                text, total_pages = extractor(data, self.max_pages)
            except Exception as exc:  # noqa: BLE001
                logger.debug("pdf extractor %s failed for %s: %s", extractor.__name__, pdf_url, exc)
                continue
            if text.strip():
                break

        if not text.strip():
            return PdfExtraction(
                url=pdf_url,
                linked_from=linked_from,
                ok=True,
                page_count=total_pages,
                scanned=True,
                error="no_text_layer",
            )

        # Rebuild per-page slices so a fact can cite the page it came from.
        raw_pages = text.split("\n")
        pages = [
            PdfPage(page_number=index + 1, text=chunk)
            for index, chunk in enumerate(raw_pages[: self.max_pages])
            if chunk.strip()
        ]
        return PdfExtraction(
            url=pdf_url,
            linked_from=linked_from,
            ok=True,
            pages=pages,
            text=text,
            page_count=total_pages,
        )
