"""Bounded breadth-first crawling for scholarship discovery.

Why this module exists
----------------------
Discovery used to fetch **one page per approved source**: the seed URL, run it
through the extractor, and move on. That is not crawling, and it is the reason
a full discovery round over every tracked country inserted roughly one new
record. A government scholarship portal almost never publishes a programme on
its homepage - the homepage is a navigation page, and the programmes live one
or two links down, behind a "Grants" or "Opportunities" or "Students" section.

So the pipeline could see, at best, the front page of each of the ~30 seeded
portals per country and nothing behind it. Widening the seed list would not have
fixed this: the yield problem is that the seeds were never followed.

What this does
--------------
For each seed, a bounded BFS that extracts links, scores them for relevance, and
returns an ordered visit list. Each visited URL is then run through exactly the
same ``_discover_single`` path as the seed, so identity resolution, dedup, the
pre-insert quality gate and the evidence rules are unchanged - a crawled page
gets no privileges a seeded one does not.

Bounds, and why each one exists
-------------------------------
Free-tier runners have finite wall-clock time (the maintenance job is capped at
45 minutes), and a crawler with no page cap is a crawler that will follow a link
into a forum. Every limit here is therefore explicit and named:

``max_depth``
    Levels below the seed. Depth 2 covers ``portal / section / programme``,
    which is where institutional sites actually put programmes.
``max_pages_per_seed``
    Pages per seed, so one sprawling portal cannot consume the whole budget.
``max_total_pages``
    Ceiling across every seed in a round, so a large catalogue of approved
    sources cannot quietly turn into an unbounded crawl.

Relevance scoring
-----------------
Following *every* same-site link would mostly fetch "About us" and "Contact".
Links are scored on scholarship vocabulary in the URL path or the anchor text,
and negative tokens (login, cart, print, privacy...) veto a link regardless of
score. Zero-score links are not followed, with one deliberate exception: a
section landing page whose anchor clearly promises listings is followed even
when its own path is generic, because that section page is precisely the
index the next level of the crawl needs.

Scope limits, stated honestly
-----------------------------
* Same-site only: the host of the seed and its subdomains. Cross-site following
  is a different and much riskier feature and is not attempted here.
* No PDF text extraction. A PDF link is followed like any other URL, but
  ``extract_scholarship_information`` works on HTML, so a PDF-hosted programme
  will usually extract poorly and be sent to review by the pre-insert gate
  rather than being guessed at.
* ``registrable`` comparison is done on the host with ``www.`` stripped. There
  is no public-suffix list available offline, so ``co.uk`` style public
  suffixes are not modelled; the effect is that ``a.co.uk`` and ``b.co.uk`` are
  *not* treated as same-site, which is the conservative direction.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Vocabulary that makes a link worth a follow. Matched against the lowercased
# path and, separately, the anchor text. Kept deliberately broad on the positive
# side and narrow on the negative side, because a false positive costs one
# wasted fetch while a false negative costs a missed programme.
SCHOLARSHIP_LINK_TOKENS: tuple[str, ...] = (
    "scholarship",
    "fellowship",
    "grant",
    "bursary",
    "studentship",
    "award",
    "funding",
    "financial-aid",
    "financial_aid",
    "fee-waiver",
    "tuition",
    "exchange",
    "mobility",
    "opportunit",
    "programme",
    "program",
    "scheme",
    "fellow",
    "students",
    "study-abroad",
    "study_abroad",
    "apply",
    "application",
)

# A link matching any of these is never followed, however well the URL scores.
# All of them are structural site furniture: following them spends budget and
# returns nothing a scholarship record could use.
EXCLUDED_LINK_TOKENS: tuple[str, ...] = (
    "login",
    "signin",
    "sign-in",
    "logout",
    "register",
    "signup",
    "sign-up",
    "account",
    "cart",
    "checkout",
    "basket",
    "privacy",
    "cookie",
    "terms",
    "disclaimer",
    "imprint",
    "copyright",
    "print",
    "search",
    "sitemap",
    "rss",
    "feed",
    "wp-admin",
    "wp-content",
    "wp-json",
    "facebook.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "instagram.com",
)

# Anchors that promise an index of programmes. These are followed even when the
# path itself is generic, because the section page is the only route to the
# programmes underneath it and the alternative is never reaching them.
LISTING_ANCHOR_HINTS: tuple[str, ...] = (
    "opportunit",
    "scholarship",
    "fellowship",
    "grant",
    "funding",
    "award",
    "programme",
    "program",
    "scheme",
    "students",
    "study",
    "financial",
)

# Anchors that mean "leave this site" in practice even without an external host.
_TERMINAL_ANCHORS: tuple[str, ...] = (
    "apply now",
    "start application",
    "submit application",
    "sign in",
    "log in",
)


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def is_same_site(url: str, seed_url: str) -> bool:
    """True when *url* is the seed's host or a subdomain of it.

    Both sides have ``www.`` stripped, so a seed of ``www.x.edu`` and a link to
    ``x.edu`` are same-site, as are ``apply.x.edu`` and ``x.edu``. A subdomain of
    a subdomain is accepted too, which is what "target university directories"
    means in practice.
    """
    try:
        seed_host = _strip_www((urlparse(seed_url).hostname or "").lower())
        host = _strip_www((urlparse(url).hostname or "").lower())
    except ValueError:
        return False
    if not seed_host or not host:
        return False
    return host == seed_host or host.endswith("." + seed_host)


def _is_followable(url: str) -> bool:
    """Reject non-HTTP schemes and URLs that cannot be meaningfully refetched."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    # A bare fragment carries no page.
    if not parsed.path and not parsed.query:
        return False
    return True


def _normalise(url: str) -> str:
    """Strip the fragment so ``/a#top`` and ``/a`` are one URL, not two."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    return urlunparse(parsed._replace(fragment=""))


def link_relevance(url: str, anchor_text: str = "") -> int:
    """Score how likely a link is to lead to a scholarship programme page.

    Returns ``0`` for "do not follow". Positive scores are ordered by strength
    so that when a budget forces truncation, the most programme-like links are
    the ones that survive.
    """
    anchor = (anchor_text or "").strip().lower()
    try:
        parsed = urlparse(url)
        # The host is part of the exclusion check, not just the path: an
        # exclusion list containing "facebook.com" is useless if only
        # `/scholarship` is searched. `extract_links` rejects cross-site links
        # separately via `is_same_site`, but relevance must stand on its own so
        # a caller using it directly is not misled.
        haystack = f"{parsed.netloc} {parsed.path} {parsed.query}".lower()
    except ValueError:
        return 0

    if any(token in anchor for token in _TERMINAL_ANCHORS):
        return 0

    combined = f"{haystack} {anchor}"
    if any(token in combined for token in EXCLUDED_LINK_TOKENS):
        return 0

    score = 0
    # Path matches are the strongest signal: a programme URL almost always
    # contains the word in the path itself.
    if any(token in haystack for token in SCHOLARSHIP_LINK_TOKENS):
        score += 3
    if any(token in anchor for token in SCHOLARSHIP_LINK_TOKENS):
        score += 2
    # An anchor that reads like a listing is worth following even when the
    # path is generic ("/index.php?page=3").
    if score == 0 and any(hint in anchor for hint in LISTING_ANCHOR_HINTS):
        score = 1

    return score


def extract_links(
    content: str,
    page_url: str,
    *,
    limit: int,
    url_filter=None,
) -> list[str]:
    """Return same-site, relevance-scored links from *content*, best first.

    ``url_filter`` is an optional predicate applied after the site check - the
    pipeline passes its approved-source registry so a subdomain that is not an
    approved source is dropped here rather than being fetched and then recorded
    as a rejected candidate.
    """
    if not content or limit <= 0:
        return []
    try:
        soup = BeautifulSoup(content, "html.parser")
    except Exception:  # noqa: BLE001 - malformed HTML must not kill a round
        logger.debug("could not parse %s for links", page_url, exc_info=True)
        return []

    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = (anchor["href"] or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        try:
            absolute = _normalise(urljoin(page_url, href))
        except ValueError:
            continue
        if not _is_followable(absolute):
            continue
        if absolute in seen:
            continue
        if not is_same_site(absolute, page_url):
            continue
        score = link_relevance(absolute, anchor.get_text(" ", strip=True))
        if score <= 0:
            continue
        if url_filter is not None and not url_filter(absolute):
            continue
        seen.add(absolute)
        scored.append((score, absolute))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [url for _, url in scored[:limit]]


@dataclass
class CrawlBudget:
    """Explicit, named crawl limits.

    These are part of the contract rather than literals buried in a loop,
    because the cost of the crawl is what decides whether the maintenance job
    fits in the free-tier wall clock.
    """

    max_depth: int = 2
    max_pages_per_seed: int = 12
    max_total_pages: int = 400

    def as_dict(self) -> dict:
        return {
            "max_depth": self.max_depth,
            "max_pages_per_seed": self.max_pages_per_seed,
            "max_total_pages": self.max_total_pages,
        }


class DeepCrawler:
    """Bounded BFS from a seed URL to an ordered list of URLs to visit.

    The crawler does not fetch anything itself beyond the pages it needs to
    read links from, and it does not decide what a page *means* - that is the
    pipeline's job. Its whole responsibility is deciding which pages are worth
    the pipeline's time.
    """

    def __init__(self, budget: CrawlBudget | None = None, url_filter=None) -> None:
        self.budget = budget or CrawlBudget()
        self.url_filter = url_filter
        self.pages_fetched = 0
        self.links_followed = 0

    def _read_links(self, url: str) -> list[str]:
        """Fetch a page purely to read its links, tolerating any failure."""
        from .official_source_fetcher import fetch_official_source

        self.pages_fetched += 1
        try:
            result = fetch_official_source(url)
        except Exception:  # noqa: BLE001 - a crawl must survive one bad page
            logger.debug("crawl could not fetch %s", url, exc_info=True)
            return []
        if not getattr(result, "success", False) or not result.content:
            return []
        # One page of links per URL is generous for a bounded crawl; the
        # pipeline re-fetches the URL it actually needs and that fetch is
        # served from the fetcher's memo cache.
        return extract_links(
            result.content,
            url,
            limit=max(self.budget.max_pages_per_seed * 2, 20),
            url_filter=self.url_filter,
        )

    def plan(self, seed_url: str) -> list[str]:
        """Return the URLs to visit for one seed, seed first.

        Ordering is breadth-first by depth and, within a depth, by descending
        relevance. When ``max_pages_per_seed`` truncates the frontier, the
        pages that survive are the most programme-like ones rather than an
        arbitrary prefix of link order.
        """
        seed = _normalise(seed_url)
        if not _is_followable(seed):
            return []

        visited: set[str] = {seed}
        order: list[str] = [seed]
        frontier: deque[tuple[str, int]] = deque([(seed, 0)])

        while frontier:
            if len(order) >= self.budget.max_pages_per_seed:
                break
            current, depth = frontier.popleft()
            if depth >= self.budget.max_depth:
                continue
            for link in self._read_links(current):
                if link in visited:
                    continue
                if len(order) >= self.budget.max_pages_per_seed:
                    break
                visited.add(link)
                order.append(link)
                self.links_followed += 1
                frontier.append((link, depth + 1))

        return order
