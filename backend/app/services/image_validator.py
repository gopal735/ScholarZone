"""Evidence-driven image validation for scholarship images.

Validates discovered image candidates against:
- HTTP reachability
- Valid image content/type (via header and optional Pillow verification)
- Official domain verification
- Contextual relevance to the exact scholarship/program
- Non-content image rejection with layered evidence scoring:
  - Banners/hero with generic site-wide semantics
  - Placeholders and default images
  - Navigation/UI elements
  - Error/placeholder images (404, 500, etc.)
  - Logos/emblems/branding
  - Social share icons
  - Open Graph/metadata thumbnails
- Duplicate/reused image detection
- Provenance/licensing evidence collection

Designed for read-only dry-run validation — never writes to the database.

The validator uses **layered evidence** rather than single-keyword filters.
Each non-content class (banner, placeholder, nav, error, logo, social, og-thumb)
has independent signal detectors that accumulate weighted evidence across
filename, URL path, dimensions, alt text, and page context. A candidate
is rejected as non-content when total evidence weight crosses a threshold,
regardless of relevance score. Legitimate scholarship images can still pass
when they produce no non-content signals.
"""

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import urlparse

import httpx
from PIL import Image

from ..services.image_analysis import analyze_image, ImageAnalysisResult, ImageClassification
from ..services.image_discovery import ImageCandidate, ImageDiscoveryService, PageFetchResult
from ..services.scholarship_image_verifier import ImageSourceType, is_official_domain, extract_domain


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

VALID_IMAGE_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
    "image/tiff",
})

MIN_IMAGE_DIMENSION = 200
MIN_IMAGE_AREA = 200 * 200
MIN_COVER_IMAGE_DIMENSION = 500
ASPECT_RATIO_MIN = 0.2
ASPECT_RATIO_MAX = 5.0

CONTENT_ILLUSTRATION_SIGNALS = (
    "students", "graduation", "campus", "study", "scholarship",
    "international", "exchange", "lecture", "classroom", "university",
    "certificate", "diploma", "graduate", "research",
    "student", "alumni", "faculty", "library", "laboratory",
)

SVG_APPROVAL_WHITELIST = frozenset({
    "erasmus-plus.ec.europa.eu",
    "a2ascholarships.iccr.gov.in",
    "studyinkorea.go.kr",
    "studyinjapan.go.jp",
    "ec.europa.eu",
    "daad.de",
})

# ---------------------------------------------------------------------------
# Non-content image detection — layered evidence system
# ---------------------------------------------------------------------------
# Each detector returns a list of (signal_label, weight) tuples. The total
# weight is summed and compared against NON_CONTENT_REJECTION_THRESHOLD to
# decide rejection. This avoids false positives where one benign keyword
# appears in a filename but the image is genuinely a content illustration.

NON_CONTENT_REJECTION_THRESHOLD = 1.5


@dataclass
class NonContentSignal:
    """A single piece of evidence that an image may be non-content."""
    label: str
    weight: float
    source: str  # "filename", "url_path", "alt_text", "html_context", "dimensions", "content_type", "discovery"


def _extract_url_parts(image_url: str) -> tuple[str, str, str]:
    """Extract path, filename, and full scan text (path+query) from a URL.

    The full scan text includes query parameters so keywords like
    orgfilename=banner_x.png or filename=gist_emblem.png are detected.
    """
    parsed = urlparse(image_url.lower())
    path = parsed.path.lower()
    filename = path.rsplit("/", 1)[-1] if "/" in path else path
    full_scan = f"{path}?{parsed.query}" if parsed.query else path
    return path, filename, full_scan


def _detect_generic_filename_signals(filename: str, full_scan: str, path: str) -> list[NonContentSignal]:
    """Detect generic hash-based filenames, country-code flags, and CMS download handlers.

    These are typically auto-generated image paths, country flag icons, or CMS
    download scripts that serve images via HTML pages — not content-specific
    scholarship images.
    """
    signals = []

    # Hash-based filenames (long alphanumeric strings before extension)
    # e.g. ac9z5dezceaz6c9z911z3a3zfecz077z889z429za0.png
    name_without_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
    if len(name_without_ext) >= 20 and name_without_ext.isalnum() and "." not in name_without_ext:
        signals.append(NonContentSignal(
            label=f"hash-based filename (len={len(name_without_ext)})",
            weight=1.5, source="filename"))

    # Timestamp-based filenames — auto-generated upload names like 20260904140825301371.png
    import re
    if re.match(r'^\d{14,20}$', name_without_ext):
        signals.append(NonContentSignal(
            label=f"timestamp-based filename ({name_without_ext})",
            weight=1.5, source="filename"))

    # Country code filenames: only 2 letters before extension, e.g. "in.png", "fr.jpg", "de.gif"
    name_lower = filename.lower()
    name_without_ext = name_lower.rsplit(".", 1)[0] if "." in name_lower else name_lower
    if len(name_without_ext) == 2 and name_without_ext.isalpha():
        signals.append(NonContentSignal(
            label=f"country-code flag filename: '{name_without_ext}'",
            weight=1.5, source="filename"))

    # CMS download handler: URL path ends in .html or .php but serves an image
    # via query params (e.g. imgpreview.do?filename=... or index.php?mode=IMG...)
    if any(path.endswith(ext) for ext in [".html", ".php", ".htm", ".do", ".jsp", ".asp"]):
        if "?" in full_scan:
            signals.append(NonContentSignal(
                label=f"CMS download handler URL: path ends in {path.rsplit('.', 1)[-1]}",
                weight=1.5, source="url_path"))

    return signals


def _detect_banner_signals(image_url: str, alt_text: str | None, html_context: str | None,
                           width: int | None, height: int | None,
                           official_source_url: str | None = None,
                           page_url: str | None = None) -> list[NonContentSignal]:
    """Detect site-wide banners and hero images that are generic, not content-specific."""
    signals = []
    path, filename, full_scan = _extract_url_parts(image_url)
    alt = (alt_text or "").lower()

    banner_kw = ["banner", "hero", "header-banner", "homepage-banner",
                 "home-banner", "site-banner", "top-banner", "divider", "section-divider",
                 "section_bg", "section-bg", "bg_", "bg-image", "bgimage",
                 "div_", "_div", "section_bg_"]

    for kw in banner_kw:
        if kw in filename:
            signals.append(NonContentSignal(
                label=f"banner/divider filename: '{kw}'",
                weight=1.5, source="filename"))
        if kw in full_scan and "/sites/" not in full_scan:
            signals.append(NonContentSignal(
                label=f"banner/divider in URL: '{kw}'",
                weight=1.5, source="url_path"))

    if "banner" in alt or "hero" in alt:
        signals.append(NonContentSignal(
            label=f"banner alt text: '{alt[:50]}'",
            weight=1.5, source="alt_text"))

    # _s suffix in filename — indicates small thumbnail variant
    if filename.endswith("_s.jpg") or filename.endswith("_s.png") or filename.endswith("_s.jpeg"):
        signals.append(NonContentSignal(
            label="thumbnail size suffix '_s' in filename",
            weight=1.5, source="filename"))

    # Thumbnail size suffix patterns: _l_1, _s_1, _m_1, _l_2, etc.
    # Common CMS pattern: <name>_<size>_<variant>.<ext>
    import re
    if re.search(r'_[lsm]_[0-9]+\.', filename):
        signals.append(NonContentSignal(
            label="thumbnail size suffix pattern (_l_1, _s_2, etc.) in filename",
            weight=1.5, source="filename"))

    # Wide aspect ratio (e.g. 16:9, 21:9) combined with "banner"/"hero" in URL
    if signals and width and height and width / height > 2.5:
        signals.append(NonContentSignal(
            label=f"wide aspect ratio ({width}x{height}) with banner keyword",
            weight=1.0, source="dimensions"))

    # Common paths that indicate site-wide hero/banner assets
    site_wide_paths = ["/common/", "/assets/images/common/", "/global/",
                       "/assets/img/banner", "/wp-content/uploads/banners", "/themes/"]
    for swp in site_wide_paths:
        if swp in full_scan:
            weight = 1.0 if swp == "/themes/" else 1.5
            signals.append(NonContentSignal(
                label=f"site-wide asset path: '{swp}'",
                weight=weight, source="url_path"))
            break

    # Homepage-specific paths: /home/ indicates site-wide homepage assets
    homepage_paths = ["/home/", "/homepage/", "/home-page/", "/_assets/images/home/"]
    for hp in homepage_paths:
        if hp in full_scan:
            signals.append(NonContentSignal(
                label=f"homepage asset path: '{hp}'",
                weight=1.5, source="url_path"))
            break

    # Dimension patterns in URL path (e.g. 1600x550, 1920x1080) combined with
    # homepage paths — indicates CMS-generated homepage banner assets rather than
    # program-specific content images.
    homepage_dim_paths = ["/home/", "/homepage/", "/_assets/images/home/", "/assets/images/home/"]
    if any(hp in full_scan for hp in homepage_dim_paths):
        dim_match = re.search(r'\d{3,5}[x-]\d{3,5}', full_scan)
        if dim_match:
            signals.append(NonContentSignal(
                label=f"homepage banner dimensions in path: '{dim_match.group()}'",
                weight=1.5, source="url_path"))

    # Image discovered from a crawled subpage rather than the primary official page
    # — no longer a rejection signal. Instead, relevance is adjusted in _check_relevance.
    return signals


def _detect_placeholder_signals(image_url: str, alt_text: str | None,
                                html_context: str | None, filename: str) -> list[NonContentSignal]:
    """Detect placeholder, sample, and default images."""
    signals = []
    _, _, full_scan = _extract_url_parts(image_url)

    placeholder_kw = ["untitled", "placeholder", "sample",
                      "placeholder-img", "sample-img", "tmp-img", "temp_img",
                      "noimage", "no-image", "image-not-available", "missing-image",
                      "img-placeholder", "placeholder_img",
                      "sample-default", "default_banner", "default-image",
                      "default_img", "default-banner", "default_placeholder"]

    for kw in placeholder_kw:
        if kw in full_scan:
            signals.append(NonContentSignal(
                label=f"placeholder in URL: '{kw}'",
                weight=2.0, source="url_path"))
            return signals

    if "placeholder" in (alt_text or "").lower():
        signals.append(NonContentSignal(
            label=f"placeholder alt text",
            weight=1.5, source="alt_text"))

    return signals


def _detect_document_image_signals(image_url: str, alt_text: str | None, filename: str) -> list[NonContentSignal]:
    """Detect document/flyer images that are scans or flyers, not photographic content.

    Filenames containing 'pamphlet', 'flyer', 'brochure', 'leaflet', 'poster',
    'recruitment', or 'saiyou' (Japanese for recruitment) indicate scanned
    document images rather than original photography.
    """
    signals = []
    _, _, full_scan = _extract_url_parts(image_url)
    name_lower = filename.lower()

    doc_kw = ["pamphlet", "flyer", "brochure", "leaflet", "poster", "recruitment",
              "saiyou", "saiyou_eng", "ejubann", "bann", "jobhunting", "job_hunting",
              "jobhuntingguide", "guideline", "manual", "handbook"]

    for kw in doc_kw:
        if kw in name_lower or kw in full_scan:
            signals.append(NonContentSignal(
                label=f"document/flyer image: '{kw}' in filename",
                weight=1.5, source="filename"))
            break

    # Administrative/system platform keywords — indicate system-generated thumbnails
    # rather than original scholarship content photography
    admin_kw = ["entopmv", "learnus", "banner_adm", "adm_banner",
                "system_image", "sys_img", "temp_image", "tmp_image"]
    for kw in admin_kw:
        if kw in name_lower or kw in full_scan:
            signals.append(NonContentSignal(
                label=f"administrative system image: '{kw}' in filename",
                weight=1.5, source="filename"))
            break

    # Numeric dimension pattern in filename (e.g., _1032-477, _800x600) is no longer
    # used as a non-content signal. Legitimate CMS-generated images frequently embed
    # dimensions in filenames (e.g., WordPress image-1024x640.jpg). Actual image
    # dimensions are verified separately in _check_image_dimensions.
    return signals


def _detect_nav_ui_signals(image_url: str, alt_text: str | None,
                           html_context: str | None, filename: str) -> list[NonContentSignal]:
    """Detect navigation and UI element images."""
    signals = []
    path = urlparse(image_url.lower()).path.lower()
    alt = (alt_text or "").lower()
    ctx = (html_context or "").lower()

    # UI element keywords — check both filename and alt text
    ui_kw = ["btn", "button", "icon", "close", "drawer", "menu", "arrow",
             "chevron", "toggle", "favicon", "sprite", "loading",
             "spinner", "avatar", "nav", "navigation", "bullet",
             "divider", "separator", "accordion", "pagination",
             "slider", "thumb", "caret", "expand",
             "collapse", "hamburger", "back-btn", "next-arrow",
             "prev-arrow", "skip-link", "pixel", "tracking-pixel"]

    combined = f"{filename} {alt} {ctx}"
    matched_kw = []

    for kw in ui_kw:
        # Match as whole words or common naming patterns (e.g. "btn-", "_btn", "btn_")
        if kw in filename or kw in alt:
            matched_kw.append(kw)

    if matched_kw:
        signals.append(NonContentSignal(
            label=f"UI element keywords: {matched_kw[:3]}",
            weight=1.5, source="filename/alt"))

    # Navigation-specific paths
    nav_paths = ["/nav/", "/icons/", "/ui/", "/assets/icons", "/img/icons",
                 "/static/icons", "/elements", "/ui-elements"]
    for np in nav_paths:
        if np in path:
            signals.append(NonContentSignal(
                label=f"navigation/icon path: '{np}'",
                weight=1.5, source="url_path"))
            break

    return signals


def _detect_error_signals(filename: str, alt_text: str | None, full_url: str) -> list[NonContentSignal]:
    """Detect error images (404, 500, etc.)."""
    signals = []
    error_kw = ["404", "403", "500", "400", "502", "503", "error",
                "not-found", "notfound", "error-page", "error_image",
                "internal-server-error", "forbidden", "gone"]

    scan_text = f"{filename} {full_url}".lower()
    for kw in error_kw:
        if kw in scan_text:
            signals.append(NonContentSignal(
                label=f"error image: '{kw}' in URL/filename",
                weight=2.0, source="filename/url"))
            return signals

    if "error" in (alt_text or "").lower():
        signals.append(NonContentSignal(
            label="error alt text",
            weight=1.5, source="alt_text"))

    return signals


def _detect_logo_emblem_signals(image_url: str, alt_text: str | None,
                                 filename: str, html_context: str | None = None) -> list[NonContentSignal]:
    """Detect logos, emblems, and branding images.

    URL-only detection is intentionally limited to avoid false positives on
    legitimate content images whose paths happen to contain 'logo' as a
    substring (e.g. 'nologo'). Signals are only generated when:
    - alt text explicitly mentions logo/emblem/brand
    - HTML context strongly indicates a logo
    - filename strongly indicates a logo (not negated by 'nologo', 'no-logo')
    - path contains explicit logo directory segments
    """
    signals = []
    path, _, full_scan = _extract_url_parts(image_url)
    filename_lower = filename.lower()
    alt_lower = (alt_text or "").lower()
    ctx_lower = (html_context or "").lower()

    # Strong filename signals — but NOT if filename indicates absence of logo
    strong_logo_filenames = ["logo", "emblem", "crest", "brand_mark",
                             "logotype", "brandmark", "symbol-mark", "coat-of-arms"]
    for kw in strong_logo_filenames:
        if filename_lower == kw or filename_lower.startswith(f"{kw}.") or filename_lower.startswith(f"{kw}_"):
            signals.append(NonContentSignal(
                label=f"logo/emblem filename: '{kw}'",
                weight=1.5, source="filename"))
            break

    # Alt text is strong signal
    if any(kw in alt_lower for kw in ["logo", "emblem", "crest", "brand", "coat of arms"]):
        signals.append(NonContentSignal(
            label=f"logo/emblem/brand alt text",
            weight=1.5, source="alt_text"))

    # HTML context signal (heading text near the image)
    if any(kw in ctx_lower for kw in ["our logo", "official logo", "university crest",
                                       "institutional emblem", "brand mark"]):
        signals.append(NonContentSignal(
            label="logo/emblem HTML context",
            weight=1.5, source="html_context"))

    # Explicit logo directory paths
    logo_paths = ["/logo/", "/logos/", "/brand/", "/emblem/", "/assets/logo/",
                  "/img/logo/", "/images/logo/", "/icons/logo/", "/logo-",
                  "/assets/logos/", "/_media/logo/"]
    for lp in logo_paths:
        if lp in path:
            signals.append(NonContentSignal(
                label=f"logo/emblem path: '{lp}'",
                weight=1.5, source="url_path"))
            break

    return signals


def _detect_social_share_signals(image_url: str, alt_text: str | None,
                                  filename: str, discovery_method: str) -> list[NonContentSignal]:
    """Detect social media share icons and social thumbnails."""
    signals = []
    _, _, full_scan = _extract_url_parts(image_url)
    social_kw = ["facebook", "twitter", "linkedin", "whatsapp", "share",
                 "social", "sharethis", "addthis", "tweet", "pin-it",
                 "vk-com", "weibo", "tumblr", "pinterest"]

    combined = f"{filename} {alt_text or ''}".lower()
    for kw in social_kw:
        if kw in combined:
            signals.append(NonContentSignal(
                label=f"social share keyword: '{kw}'",
                weight=1.5, source="filename/alt"))
            break

    # Social thumbnail dimension patterns in URL path/query
    social_dims = any(dim in full_scan for dim in ["327x151", "327x152", "1200x630",
                       "1003x490", "1000x521", "200x200", "600x315"])
    if social_dims:
        signals.append(NonContentSignal(
            label=f"social thumbnail dimensions in URL",
            weight=1.0, source="url_path"))

    # Twitter:card or facebook-specific discovery methods
    if discovery_method in ("twitter:image", "facebook:image"):
        signals.append(NonContentSignal(
            label=f"social discovery method: {discovery_method}",
            weight=1.5, source="discovery"))

    return signals


def _detect_infrastructure_signals(image_url: str, filename: str, full_scan: str, path: str) -> list[NonContentSignal]:
    """Detect infrastructure/proxy URLs and CMS derivative paths that serve thumbnails or UI assets.

    These are not real content image sources — they are CDN proxies, CMS image
    style derivatives, or thumbnail generation endpoints that produce small UI
    variants rather than scholarship-specific photography.
    """
    signals = []

    # Next.js image optimization proxy: /_next/image?url=...&w=...&q=...
    if "/_next/image" in path:
        signals.append(NonContentSignal(
            label="Next.js image proxy URL (_next/image)",
            weight=1.5, source="url_path"))

    # Drupal image styles: /styles/<style_name>/... — these are CMS-generated derivatives
    # Only flag actual UI-style names, not standard content styles like responsive_large
    drupal_ui_styles = [
        "mobile_menu_image", "desktop_paragraph", "mobile_bloc_mi_la",
        "mobile_visuel_priority", "tablet_menu", "mobile_menu_background",
        "media_thumbnail", "media_square",
        "teaser", "thumbnail", "icon",
    ]
    for style in drupal_ui_styles:
        if style in full_scan:
            signals.append(NonContentSignal(
                label=f"Drupal CMS style path: '{style}'",
                weight=1.5, source="url_path"))
            break

    # Thumbnail dimension patterns in query parameters: h=XXX&w=XXX or w=XXX&h=XXX
    # where both dimensions are under 600px — indicates a generated thumbnail
    import re
    dim_pattern = re.search(r'[?&](?:h|height|w|width)=(\d+)', full_scan)
    if dim_pattern:
        dims = re.findall(r'[?&](?:h|height)=(\d+)|[?&](?:w|width)=(\d+)', full_scan)
        if dims:
            all_dims = []
            for d in dims:
                for v in d:
                    if v:
                        all_dims.append(int(v))
            if len(all_dims) >= 2 and all(d < 800 for d in all_dims):
                max_dim = max(all_dims)
                if max_dim < 800:
                    signals.append(NonContentSignal(
                        label=f"Thumbnail dimensions in URL: {all_dims}",
                        weight=1.5, source="url_path"))

    # img_ pattern in filename — common UI/generic image asset prefix
    # Matches patterns like: img_stem, uic_img_stem, img_home, etc.
    import re
    if re.search(r'(?:^|_)img[_-]', filename) or re.search(r'img[_-](?:stem|home|main|thumb|icon|bg|bg_|logo|pic)', filename):
        signals.append(NonContentSignal(
            label=f"Generic UI image pattern: 'img_' in filename",
            weight=1.5, source="filename"))

    return signals


def _detect_og_thumbnail_signals(image_url: str, filename: str,
                                  discovery_method: str) -> list[NonContentSignal]:
    """Detect Open Graph and metadata thumbnails that are preview cards, not content.

    Only flags when the URL/filename contains og-specific keywords OR the
    image is discovered via og:image/twitter:image AND has generic thumbnail paths.
    A legitimate content image discovered through og:image meta tag is NOT flagged.
    """
    signals = []
    _, _, full_scan = _extract_url_parts(image_url)
    path = urlparse(image_url.lower()).path.lower()
    og_url_keywords = ["og:image", "og-image", "ogimg", "og_thumbnail",
                       "og-thumb", "ogimage", "meta-thumbnail", "preview-card",
                       "social-preview", "link-preview", "share-preview",
                       "facebook-share", "twitter-card"]

    # Flag og: patterns only when they appear in the URL itself
    for kw in og_url_keywords:
        if kw in full_scan:
            signals.append(NonContentSignal(
                label=f"OG/social thumbnail keyword: '{kw}'",
                weight=1.5, source="url_path"))
            break

    # og:image discovery method combined with generic-looking thumbnail paths
    if discovery_method == "og:image" and any(p in path for p in ["/common/", "/assets/common", "/default/", "/og", "/og-image", "/ogimg", "/og_thumb"]):
        signals.append(NonContentSignal(
            label="og:image from common/default/og path",
            weight=1.5, source="url_path"))

    return signals


def _detect_non_content_signals(
    candidate: ImageCandidate,
    width: int | None,
    height: int | None,
    official_source_url: str | None = None,
) -> list[NonContentSignal]:
    """Run all non-content signal detectors and accumulate evidence."""
    image_url = candidate.image_url
    alt_text = candidate.alt_text
    html_context = candidate.html_context
    discovery_method = candidate.discovery_method

    path, filename, full_scan = _extract_url_parts(image_url)

    signals: list[NonContentSignal] = []

    signals.extend(_detect_banner_signals(image_url, alt_text, html_context, width, height,
                                          official_source_url=official_source_url,
                                          page_url=candidate.page_url))
    signals.extend(_detect_placeholder_signals(image_url, alt_text, html_context, filename))
    signals.extend(_detect_nav_ui_signals(image_url, alt_text, html_context, filename))
    signals.extend(_detect_error_signals(filename, alt_text, full_scan))
    signals.extend(_detect_logo_emblem_signals(image_url, alt_text, filename, html_context=html_context))
    signals.extend(_detect_social_share_signals(image_url, alt_text, filename, discovery_method))
    signals.extend(_detect_og_thumbnail_signals(image_url, filename, discovery_method))
    signals.extend(_detect_generic_filename_signals(filename, full_scan, path))
    signals.extend(_detect_infrastructure_signals(image_url, filename, full_scan, path))
    signals.extend(_detect_document_image_signals(image_url, alt_text, filename))

    return signals


class ValidationStatus(str, Enum):
    APPROVED = "approved"
    HUMAN_REVIEW = "human_review"
    REJECTED = "rejected"
    NOT_CHECKED = "not_checked"


@dataclass
class ImageValidationResult:
    candidate: ImageCandidate
    is_reachable: bool = False
    http_status: int | None = None
    content_type: str | None = None
    is_valid_image: bool = False
    is_official_domain: bool = False
    image_domain: str | None = None
    source_domain: str | None = None
    width: int | None = None
    height: int | None = None
    is_generic_image: bool = False
    is_ui_asset: bool = False
    is_svg: bool = False
    is_svg_content_illustration: bool = False
    aspect_ratio: float | None = None
    is_duplicate: bool = False
    duplicate_of: str | None = None
    licensing_status: str = "licensing_unknown"
    licensing_evidence: str | None = None
    relevance_score: float = 0.0
    relevance_notes: list[str] = field(default_factory=list)
    confidence: str = "LOW"
    status: ValidationStatus = ValidationStatus.NOT_CHECKED
    rejection_reasons: list[str] = field(default_factory=list)
    human_review_reason: str | None = None
    checked_at: datetime | None = None
    non_content_signals: list[NonContentSignal] = field(default_factory=list)
    non_content_total_weight: float = 0.0
    non_content_logo_weight: float = 0.0
    file_size_bytes: int | None = None
    image_analysis: ImageAnalysisResult | None = None
    image_kind: str | None = None
    result_id: int = 0


@dataclass
class ConfidenceDecision:
    """Represents the final confidence-based decision for an image candidate."""
    confidence: str = "LOW"
    status: ValidationStatus = ValidationStatus.REJECTED
    reason: str = ""

    @property
    def is_approved(self) -> bool:
        return self.status == ValidationStatus.APPROVED

    @property
    def needs_human_review(self) -> bool:
        return self.status == ValidationStatus.HUMAN_REVIEW


class ImageValidator:
    """Validates image candidates for official scholarship usage."""

    def __init__(self, seen_images: dict[str, int] | None = None, timeout: float = 30.0):
        self.timeout = timeout
        self._seen_images: dict[str, int] = seen_images or {}
        self._results: list[ImageValidationResult] = []

    def validate_candidate(
        self,
        candidate: ImageCandidate,
        scholarship_title: str | None = None,
        official_source_url: str | None = None,
    ) -> ImageValidationResult:
        """Perform full validation of a single image candidate."""
        result = ImageValidationResult(
            candidate=candidate,
            checked_at=datetime.now(timezone.utc),
        )

        result.source_domain = extract_domain(official_source_url) if official_source_url else None
        result.image_domain = extract_domain(candidate.image_url)

        result = self._check_reachability(result)
        if not result.is_reachable:
            result.status = ValidationStatus.REJECTED
            result.confidence = "LOW"
            result.rejection_reasons.append(f"Image unreachable (HTTP {result.http_status})")
            result.checked_at = datetime.now(timezone.utc)
            self._finalize_decision(result, scholarship_title, official_source_url)
            return result

        result = self._check_content_type(result)
        result = self._check_official_domain(result)
        result = self._check_image_dimensions(result)
        result = self._check_image_content(result)
        result = self._check_non_content_signals(result, official_source_url)
        result = self._check_svg_safety(result, scholarship_title)
        result = self._check_duplicate(result)
        result = self._check_licensing(result)
        result = self._check_relevance(result, scholarship_title, official_source_url)
        result.image_kind = self._classify_image_kind(result)
        if result.image_kind == "official_logo":
            result = self._validate_logo_fallback(result, [result])
        self._finalize_decision(result, scholarship_title, official_source_url)

        return result

    def validate_candidates(
        self,
        candidates: list[ImageCandidate],
        scholarship_title: str | None = None,
        official_source_url: str | None = None,
    ) -> list[ImageValidationResult]:
        """Validate a list of candidates, returning results in priority order."""
        results = []
        for idx, candidate in enumerate(candidates):
            result = self.validate_candidate(candidate, scholarship_title, official_source_url)
            result.result_id = idx + 1
            results.append(result)
            if result.is_duplicate:
                self._seen_images[candidate.image_url] = self._seen_images.get(candidate.image_url, 0) + 1

        for result in results:
            result.image_kind = self._classify_image_kind(result)
            if result.image_kind == "official_logo":
                result = self._validate_logo_fallback(result, results)

        results.sort(key=lambda r: (
            r.status.value != ValidationStatus.APPROVED.value,
            r.status.value != ValidationStatus.HUMAN_REVIEW.value,
            {"program_image": 0, "official_banner": 1, "official_logo": 2}.get(r.image_kind or "", 3),
            -r.relevance_score,
        ))
        return results

    def find_best_result(self, results: list[ImageValidationResult]) -> ImageValidationResult | None:
        """Return the highest-priority valid result, or None."""
        approved = [r for r in results if r.status == ValidationStatus.APPROVED]
        if approved:
            return max(approved, key=lambda r: r.relevance_score)
        reviewed = [r for r in results if r.status == ValidationStatus.HUMAN_REVIEW]
        if reviewed:
            return max(reviewed, key=lambda r: r.relevance_score)
        return None

    def _check_reachability(self, result: ImageValidationResult) -> ImageValidationResult:
        try:
            response = httpx.head(
                result.candidate.image_url,
                headers={"User-Agent": BROWSER_UA},
                timeout=self.timeout,
                follow_redirects=True,
            )
            result.http_status = response.status_code
            result.content_type = response.headers.get("content-type")
            result.is_reachable = response.status_code == 200
        except httpx.RequestError:
            result.http_status = None
            result.is_reachable = False
        return result

    def _check_content_type(self, result: ImageValidationResult) -> ImageValidationResult:
        if not result.content_type:
            result.is_valid_image = False
            result.rejection_reasons.append("No content-type header")
            return result

        content_type = result.content_type.split(";")[0].strip().lower()
        result.content_type = content_type

        if content_type == "image/svg+xml":
            result.is_svg = True

        if content_type not in VALID_IMAGE_TYPES:
            result.is_valid_image = False
            result.rejection_reasons.append(f"Invalid content-type: {content_type}")
        else:
            result.is_valid_image = True

        return result

    def _check_official_domain(self, result: ImageValidationResult) -> ImageValidationResult:
        if result.image_domain and is_official_domain(result.image_domain):
            result.is_official_domain = True
        else:
            result.is_official_domain = False
            result.rejection_reasons.append(f"Image domain not official: {result.image_domain}")
        return result

    def _check_image_dimensions(self, result: ImageValidationResult) -> ImageValidationResult:
        if result.is_svg:
            return result

        if result.candidate.width and result.candidate.height:
            result.width = result.candidate.width
            result.height = result.candidate.height

        if result.width is None or result.height is None:
            self._fetch_image_dimensions(result)

        if result.width and result.height:
            if result.width < MIN_IMAGE_DIMENSION or result.height < MIN_IMAGE_DIMENSION:
                result.is_generic_image = True
                result.rejection_reasons.append(
                    f"Image too small ({result.width}x{result.height})"
                )

            if result.width > 1 and result.height > 1:
                ratio = result.width / result.height
                result.aspect_ratio = round(ratio, 4)
                if ratio < ASPECT_RATIO_MIN or ratio > ASPECT_RATIO_MAX:
                    result.is_generic_image = True
                    result.rejection_reasons.append(
                        f"Extreme aspect ratio ({ratio:.2f}:1) — likely UI sprite/icon"
                    )

        if result.is_svg and result.width and result.height:
            ratio = result.width / result.height if result.height > 0 else 0
            result.aspect_ratio = round(ratio, 4)
            if ratio < ASPECT_RATIO_MIN or ratio > ASPECT_RATIO_MAX:
                result.is_generic_image = True
                result.rejection_reasons.append(
                    f"SVG extreme aspect ratio ({ratio:.2f}:1)"
                )

        return result

    def _fetch_image_dimensions(self, result: ImageValidationResult) -> None:
        """Fetch actual image dimensions when not provided by HTML attributes."""
        if result.width and result.height:
            return
        if not result.is_reachable or not result.candidate.image_url:
            return
        try:
            with httpx.stream(
                "GET",
                result.candidate.image_url,
                headers={"User-Agent": BROWSER_UA},
                timeout=self.timeout,
                follow_redirects=True,
            ) as response:
                if response.status_code != 200:
                    return
                content = response.read()
                if not content:
                    return
                result.file_size_bytes = len(content)
                try:
                    img = Image.open(io.BytesIO(content))
                    result.width = img.width
                    result.height = img.height
                except Exception:
                    pass
                if result.image_analysis is None and not result.is_svg:
                    try:
                        result.image_analysis = analyze_image(
                            result.candidate.image_url,
                            timeout=self.timeout,
                            content_length=result.file_size_bytes,
                            content=content,
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    @staticmethod
    def _safe_fmt(value, fmt, fallback="N/A"):
        if value is None:
            return fallback
        return f"{value:{fmt}}"

    def _check_image_content(self, result: ImageValidationResult) -> ImageValidationResult:
        """Apply image analysis results to validation signals.

        Skips HTTP fetch when analysis was already performed during dimension
        detection in _fetch_image_dimensions.
        """
        if result.is_svg:
            return result
        if not result.is_reachable or not result.is_valid_image or not result.is_official_domain:
            return result
        if result.is_generic_image or result.is_ui_asset:
            return result
        if result.non_content_total_weight >= NON_CONTENT_REJECTION_THRESHOLD:
            return result
        if result.image_analysis is not None:
            analysis = result.image_analysis
        else:
            analysis = analyze_image(
                result.candidate.image_url,
                timeout=self.timeout,
                content_length=result.file_size_bytes,
            )
            result.image_analysis = analysis

        if analysis.is_likely_ui:
            result.is_ui_asset = True
            result.rejection_reasons.append(
                f"Image analysis: likely UI asset (colors={self._safe_fmt(analysis.unique_colors, 'd')}, "
                f"size={self._safe_fmt(analysis.file_size_bytes, 'd')}, "
                f"edges={self._safe_fmt(analysis.edge_density, '.3f')})"
            )

        if analysis.is_likely_logo:
            result.is_generic_image = True
            result.rejection_reasons.append(
                f"Image analysis: likely logo/graphic (colors={self._safe_fmt(analysis.unique_colors, 'd')}, "
                f"variance={self._safe_fmt(analysis.color_variance, '.1f')})"
            )

        if analysis.is_likely_photo:
            score = min(result.relevance_score * 1.05, 1.0)
            result.relevance_score = round(score, 4)
            result.relevance_notes.append(
                f"Image analysis: content photograph detected (colors={self._safe_fmt(analysis.unique_colors, 'd')}, "
                f"variance={self._safe_fmt(analysis.color_variance, '.1f')})"
            )

        return result

    def _classify_image_kind(self, result: ImageValidationResult) -> str | None:
        """Classify the image kind: program_image, official_banner, or official_logo.

        Classification rules:
        - program_image: content photograph, illustration, or program-specific photo
        - official_banner: hero/banner image, but only if it appears to be program-specific
        - official_logo: logo, emblem, crest, brand mark — ONLY as fallback
        - None: cannot classify or rejected as non-content
        """
        if result.is_svg and not result.is_svg_content_illustration:
            return None

        url_lower = result.candidate.image_url.lower()
        filename = urlparse(url_lower).path.rsplit("/", 1)[-1]
        path = urlparse(url_lower).path.lower()
        alt_lower = (result.candidate.alt_text or "").lower()
        ctx_lower = (result.candidate.html_context or "").lower()

        logo_signals = result.non_content_signals + _detect_logo_emblem_signals(
            result.candidate.image_url,
            result.candidate.alt_text,
            filename,
            html_context=result.candidate.html_context,
        )
        logo_weight = sum(s.weight for s in logo_signals if s.label.startswith("logo") or s.label.startswith("emblem") or s.label.startswith("brand"))

        banner_signals = _detect_banner_signals(
            url_lower,
            result.candidate.alt_text,
            result.candidate.html_context,
            result.width,
            result.height,
            official_source_url=result.source_domain,
            page_url=result.candidate.page_url,
        )
        banner_weight = sum(s.weight for s in banner_signals)

        if logo_weight > 0 and logo_weight >= banner_weight:
            return "official_logo"

        favicon_social_patterns = [
            "favicon", "apple-touch-icon", "icon-", "-icon",
            "facebook", "twitter", "linkedin", "instagram", "youtube",
            "pinterest", "tiktok", "snapchat", "whatsapp",
        ]
        combined_check = f"{filename} {alt_lower}".lower()
        if any(p in combined_check for p in favicon_social_patterns):
            return "official_logo"

        if banner_weight > 0 and result.relevance_score >= 0.4:
            return "official_banner"

        if result.image_analysis and result.image_analysis.is_likely_photo:
            return "program_image"

        if result.relevance_score >= 0.5:
            return "program_image"

        return None

    def _validate_logo_fallback(self, result: ImageValidationResult, all_results: list[ImageValidationResult]) -> ImageValidationResult:
        """Validate logo fallback rules.

        A logo is ONLY acceptable as a fallback when:
        1. No program_image or official_banner exists with HIGH or MEDIUM confidence
        2. The logo belongs to the scholarship/provider/university/government (not third-party)
        3. It is not a favicon, UI icon, social icon, or unrelated organization logo

        Rejection reasons are added to the result if the logo is invalid.
        """
        if result.image_kind != "official_logo":
            return result

        has_better_candidate = any(
            r for r in all_results
            if r.result_id != result.result_id
            and r.image_kind in ("program_image", "official_banner")
            and r.confidence in ("HIGH", "MEDIUM")
            and r.status in (ValidationStatus.APPROVED, ValidationStatus.HUMAN_REVIEW)
        )

        if has_better_candidate:
            result.rejection_reasons.append(
                "Logo rejected: program image or banner candidate exists with higher priority"
            )
            result.confidence = "LOW"
            result.status = ValidationStatus.REJECTED
            result.image_kind = None
            return result

        third_party_patterns = [
            "favicon", "apple-touch-icon", "icon-", "-icon", "social", "share",
            "facebook", "twitter", "linkedin", "instagram", "youtube",
            "pinterest", "tiktok", "snapchat", "whatsapp",
        ]
        combined_check = f"{result.candidate.image_url.lower()} {result.candidate.alt_text or ''}".lower()
        for pattern in third_party_patterns:
            if pattern in combined_check:
                result.rejection_reasons.append(
                    f"Third-party/favicon/social icon rejected: '{pattern}' detected"
                )
                result.confidence = "LOW"
                result.status = ValidationStatus.REJECTED
                result.image_kind = None
                return result

        image_domain = result.image_domain or ""
        source_domain = result.source_domain or ""
        if source_domain and image_domain:
            source_parts = source_domain.replace("www.", "").split(".")
            image_parts = image_domain.replace("www.", "").split(".")
            if not any(
                sp in image_parts or image_domain.endswith(f".{sp}") or image_domain == sp or image_domain.endswith(sp)
                for sp in source_parts
                if sp
            ):
                result.rejection_reasons.append(
                    f"Logo domain mismatch: image on {image_domain}, source on {source_domain}"
                )
                result.confidence = "LOW"
                result.status = ValidationStatus.REJECTED
                result.image_kind = None
                return result

        return result

    def _check_non_content_signals(self, result: ImageValidationResult, official_source_url: str | None = None) -> ImageValidationResult:
        signals = _detect_non_content_signals(
            result.candidate,
            width=result.width,
            height=result.height,
            official_source_url=official_source_url,
        )
        
        # Low-resolution image: too small to be a cover image
        check_width = result.width or result.candidate.width
        check_height = result.height or result.candidate.height
        if check_width and check_height:
            min_dim = min(check_width, check_height)
            if min_dim < MIN_COVER_IMAGE_DIMENSION:
                signals.append(NonContentSignal(
                    label=f"Low resolution ({check_width}x{check_height}) — too small for cover",
                    weight=1.5, source="dimensions"))

        logo_signals = [s for s in signals if s.label.startswith("logo") or s.label.startswith("emblem") or s.label.startswith("brand")]
        non_logo_signals = [s for s in signals if s not in logo_signals]

        result.non_content_signals = signals
        result.non_content_total_weight = round(sum(s.weight for s in non_logo_signals), 4)
        result.non_content_logo_weight = round(sum(s.weight for s in logo_signals), 4)

        if result.non_content_total_weight >= NON_CONTENT_REJECTION_THRESHOLD:
            result.is_generic_image = True
            result.is_ui_asset = True
            signal_labels = "; ".join(s.label for s in non_logo_signals[:3])
            result.rejection_reasons.append(
                f"Non-content image (evidence weight {result.non_content_total_weight:.1f}/"
                f"{NON_CONTENT_REJECTION_THRESHOLD}): {signal_labels}"
            )

        return result

    def _check_svg_safety(self, result: ImageValidationResult, scholarship_title: str | None) -> ImageValidationResult:
        if not result.is_svg:
            return result

        if result.is_ui_asset or result.is_generic_image:
            result.rejection_reasons.append("SVG UI/generic asset — auto-rejected")
            return result

        image_url_lower = result.candidate.image_url.lower()
        path = urlparse(image_url_lower).path.lower()
        filename = path.rsplit("/", 1)[-1] if "/" in path else path

        matched_signals = []
        combined_text = (filename + " " + (result.candidate.alt_text or "")).lower()
        for signal in CONTENT_ILLUSTRATION_SIGNALS:
            if signal in combined_text:
                matched_signals.append(signal)
                result.is_svg_content_illustration = True

        image_domain = extract_domain(result.candidate.image_url)
        if image_domain and image_domain.lower() in SVG_APPROVAL_WHITELIST:
            result.rejection_reasons.append("SVG on whitelisted domain — requires HUMAN_REVIEW, never auto-approved")
            result.human_review_reason = "SVG image — manual verification required"
            return result

        if not result.is_svg_content_illustration:
            result.rejection_reasons.append(
                f"SVG without content illustration signals ({filename}) — auto-rejected"
            )

        return result

    def _check_duplicate(self, result: ImageValidationResult) -> ImageValidationResult:
        count = self._seen_images.get(result.candidate.image_url, 0)
        if count > 0:
            result.is_duplicate = True
            result.duplicate_of = result.candidate.image_url
        return result

    def _check_licensing(self, result: ImageValidationResult) -> ImageValidationResult:
        result.licensing_status = "licensing_unknown"
        result.licensing_evidence = None

        page_fetcher = self._get_page_fetcher()
        if page_fetcher and result.candidate.page_url:
            page_result = page_fetcher.fetch(result.candidate.page_url)
            if page_result.content:
                licensing = self._detect_licensing_from_html(
                    page_result.content, result.candidate.image_url
                )
                if licensing:
                    result.licensing_status, evidence = licensing
                    result.licensing_evidence = evidence

        return result

    def _detect_licensing_from_html(self, html: str, image_url: str) -> tuple[str, str] | None:
        import re
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        license_text = soup.find(attrs={"rel": "license"})
        if license_text:
            return ("licensing_known", f"License link found: {license_text.get_text(strip=True)[:200]}")

        copyright_patterns = [
            r"(?:©|copyright)\s*\d{4}",
            r"(?:all rights reserved)",
            r"(?:cc[ -]?by)",
            r"(?:cc[ -]?0)",
            r"(?:public domain)",
            r"(?:royalty.free)",
        ]
        full_text = soup.get_text(strip=True).lower()
        for pattern in copyright_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                match = re.search(pattern, full_text, re.IGNORECASE)
                return ("licensing_known", f"Copyright/license text found: '{match.group()}'")

        license_meta = soup.find("meta", attrs={"property": "og:license"})
        if license_meta and license_meta.get("content"):
            return ("licensing_known", f"og:license meta tag: {license_meta['content'][:200]}")

        return None

    def _check_relevance(self, result: ImageValidationResult, scholarship_title: str | None, official_source_url: str | None) -> ImageValidationResult:
        score = 1.0
        notes = []

        if result.is_generic_image:
            score *= 0.3
            notes.append("Non-content image signal — relevance severely penalized")

        if result.is_duplicate:
            score *= 0.2
            notes.append("Image reused across scholarships")

        if not result.is_official_domain:
            score *= 0.3
            notes.append("Non-official image domain")

        if not result.is_valid_image:
            score = 0.0
            notes.append("Invalid image content-type")

        if result.is_svg:
            score *= 0.3
            notes.append("SVG content — relevance penalized (requires HUMAN_REVIEW)")

        if scholarship_title:
            title_keywords = [w.lower() for w in scholarship_title.split() if len(w) > 3]
            if title_keywords and result.candidate.html_context:
                context_lower = result.candidate.html_context.lower()
                matched = sum(1 for kw in title_keywords if kw in context_lower)
                if matched:
                    score *= 1.5
                    notes.append(f"Page context matches {matched} title keywords")
                else:
                    score *= 0.7
                    notes.append("Page context does not match scholarship title keywords")

            filename = urlparse(result.candidate.image_url).path.lower().rsplit("/", 1)[-1]
            if title_keywords:
                filename_matches = sum(1 for kw in title_keywords if kw in filename)
                if filename_matches >= 2:
                    score *= 1.2
                    notes.append(f"Filename matches {filename_matches} title keywords")

            if result.candidate.alt_text:
                alt_lower = result.candidate.alt_text.lower()
                alt_matches = sum(1 for kw in title_keywords if kw in alt_lower)
                if alt_matches >= 2:
                    score *= 1.1
                    notes.append(f"Alt text matches {alt_matches} title keywords")

        if result.candidate.discovery_method == "og:image":
            score *= 1.3
            notes.append("Found via og:image meta tag")
        elif result.candidate.discovery_method == "json-ld":
            score *= 1.2
            notes.append("Found via JSON-LD structured data")

        if result.candidate.alt_text:
            score *= 1.1
            notes.append("Has alt text")
        else:
            score *= 0.9
            notes.append("No alt text")

        # Prefer images from the primary official program page over generic
        # crawled-site assets discovered on subpages.
        if official_source_url and result.candidate.page_url:
            parsed_official = urlparse(official_source_url)
            parsed_page = urlparse(result.candidate.page_url)
            official_norm = f"{parsed_official.netloc.lower()}{parsed_official.path.rstrip('/')}"
            page_norm = f"{parsed_page.netloc.lower()}{parsed_page.path.rstrip('/')}"
            if official_norm == page_norm:
                score *= 1.2
                notes.append("Image from primary program page")
            else:
                score *= 0.9
                notes.append("Image discovered from official subpage (minor relevance reduction)")

        result.relevance_score = round(min(score, 1.0), 4)
        result.relevance_notes.extend(notes)
        return result

    def _verify_image_content_type(self, result: ImageValidationResult) -> None:
        """Verify actual response content-type via GET.

        Some servers return image content-type on HEAD but HTML/error on GET.
        This check is only performed for candidates that passed initial screening
        and are about to be approved or sent to human review, to avoid the cost
        of verifying every candidate.
        """
        if not result.is_reachable or not result.content_type:
            return
        try:
            response = httpx.get(
                result.candidate.image_url,
                headers={"User-Agent": BROWSER_UA},
                timeout=self.timeout,
                follow_redirects=True,
            )
            actual_ct = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if actual_ct not in VALID_IMAGE_TYPES and actual_ct != "image/svg+xml":
                result.is_valid_image = False
                result.rejection_reasons.append(
                    f"Non-image response (HTTP {response.status_code}, CT: {actual_ct})"
                )
        except Exception:
            pass

    def _finalize_decision(self, result: ImageValidationResult, scholarship_title: str | None, official_source_url: str | None) -> None:
        if not result.is_reachable:
            result.confidence = "LOW"
            result.status = ValidationStatus.REJECTED
            return

        if not result.is_valid_image:
            result.confidence = "LOW"
            result.status = ValidationStatus.REJECTED
            return

        if not result.is_official_domain:
            result.confidence = "LOW"
            result.status = ValidationStatus.REJECTED
            return

        if result.is_ui_asset or (result.is_generic_image and result.non_content_logo_weight == 0):
            result.confidence = "LOW"
            result.status = ValidationStatus.REJECTED
            return

        if result.is_svg:
            if result.is_svg_content_illustration and result.relevance_score >= 0.5:
                result.confidence = "MEDIUM"
                result.status = ValidationStatus.HUMAN_REVIEW
                result.human_review_reason = result.human_review_reason or "SVG content image — manual verification required"
            else:
                result.confidence = "LOW"
                result.status = ValidationStatus.REJECTED
            return

        if result.is_duplicate:
            result.confidence = "LOW"
            result.status = ValidationStatus.REJECTED
            return

        # Temporarily disabled for performance testing
        # self._verify_image_content_type(result)
        # if not result.is_valid_image:
        #     result.confidence = "LOW"
        #     result.status = ValidationStatus.REJECTED
        #     return

        licensing = result.licensing_status

        if licensing == "licensing_unknown":
            if result.relevance_score >= 0.8:
                result.confidence = "MEDIUM"
                result.status = ValidationStatus.HUMAN_REVIEW
                result.human_review_reason = "Licensing unclear — needs human review"
            else:
                result.confidence = "LOW"
                result.status = ValidationStatus.REJECTED
                result.rejection_reasons.append("Relevance score too low with unknown licensing")
            return

        if result.relevance_score >= 0.8:
            result.confidence = "HIGH"
            result.status = ValidationStatus.APPROVED
        elif result.relevance_score >= 0.5:
            result.confidence = "MEDIUM"
            result.status = ValidationStatus.HUMAN_REVIEW
            result.human_review_reason = "Moderate relevance — needs human review"
        else:
            result.confidence = "LOW"
            result.status = ValidationStatus.REJECTED
            result.rejection_reasons.append("Relevance score below threshold")

        if result.image_kind == "official_logo" and result.status == ValidationStatus.APPROVED:
            result.status = ValidationStatus.HUMAN_REVIEW
            result.human_review_reason = result.human_review_reason or "Logo fallback requires admin review"
            result.confidence = "MEDIUM"

    def _get_page_fetcher(self):
        return _PageFetcher(timeout=self.timeout)


class _PageFetcher:
    """Lightweight page fetcher for licensing checks — reuses ImageDiscoveryService."""

    def __init__(self, timeout: float = 30.0):
        self._service = ImageDiscoveryService(timeout=timeout)

    def fetch(self, url: str) -> PageFetchResult:
        return self._service.fetch_page(url)


def determine_image_source_type(domain: str | None) -> ImageSourceType | None:
    """Determine the ImageSourceType based on the image's domain."""
    if not domain:
        return None
    domain = domain.lower()

    if domain == "erasmus-plus.ec.europa.eu" or domain.endswith(".europa.eu"):
        return ImageSourceType.OFFICIAL_SCHOLARSHIP

    if "iccr" in domain:
        return ImageSourceType.OFFICIAL_SCHOLARSHIP

    if "daad" in domain:
        return ImageSourceType.OFFICIAL_PROVIDER

    if domain in ("studyinkorea.go.kr",) or "studyinkorea" in domain:
        return ImageSourceType.OFFICIAL_SCHOLARSHIP

    if domain in ("studyinjapan.go.jp",) or "studyinjapan" in domain:
        return ImageSourceType.OFFICIAL_SCHOLARSHIP

    if domain.endswith(".gov") or domain.endswith(".go.kr") or domain.endswith(".go.jp"):
        return ImageSourceType.OFFICIAL_GOVERNMENT

    if domain.endswith(".ac.kr") or domain.endswith(".ac.jp") or domain.endswith(".ac.cn"):
        return ImageSourceType.OFFICIAL_UNIVERSITY

    if domain.endswith(".edu"):
        return ImageSourceType.OFFICIAL_UNIVERSITY

    return None
