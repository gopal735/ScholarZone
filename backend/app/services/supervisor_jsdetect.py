"""Deciding whether a served page is a client-side shell.

The previous design used one signal - visible text divided by markup - and that
was too brittle in both directions. A sparse but genuinely server-rendered page
looks identical to a shell, and a heavy server-rendered page looks nothing like
one.

So this is a small, deterministic classifier over several independent signals,
each of which is cheap and each of which is recorded so a decision can be
explained rather than asserted. The signals are:

1. **text density** - visible characters per byte of markup.
2. **app-container emptiness** - a root element such as ``#app``, ``#root``,
   ``#__next`` or ``#__nuxt`` that exists and has no text.
3. **script weight** - script bytes as a share of the document.
4. **hydration markers** - embedded state blobs that only a client framework
   consumes.
5. **bundle references** - framework bundle names in script sources.
6. **loading markers** - elements that say the content is still arriving.

Two rules keep it honest:

* **A shell is a strong claim.** Every one of the signals above is evidence of
  client-side rendering, and a page needs either a very low text density *and* at
  least one corroborating signal, or several corroborating signals, before it is
  called a shell. An ordinary empty directory - a real page that genuinely lists
  nobody - has prose, a heading and no app container, so it is not a shell.
* **A shell is not a negative.** The caller turns this into
  ``SOURCE_REQUIRES_RENDERING``. It never becomes "no professors exist".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

#: Below this, visible text is too sparse to be server-rendered content.
SPARSE_TEXT_RATIO = 0.05

#: Above this, the document is mostly script.
SCRIPT_HEAVY_RATIO = 0.35

#: Root elements a client framework mounts into and leaves empty server-side.
APP_CONTAINER_IDS = ("app", "root", "__next", "__nuxt", "application", "main-app", "ember-app")

#: Hydration state a client framework consumes. Its presence with no content is a
#: strong shell signal.
HYDRATION_MARKERS = (
    "__NEXT_DATA__",
    "__NUXT__",
    "__INITIAL_STATE__",
    "__PRELOADED_STATE__",
    "__APOLLO_STATE__",
    "window.__NUXT",
    "window.__INITIAL_STATE__",
    "self.__next_f",
)

#: Framework bundle references, from script src or inline code.
BUNDLE_MARKERS = (
    "_next/static",
    "/_nuxt/",
    "webpack",
    "runtime.js",
    "main.js?v=",
    "app.bundle.js",
    "vendor.bundle.js",
    "polyfills.bundle.js",
)

#: Text a page shows while its content is still being fetched.
LOADING_MARKERS = (
    "loading",
    "please wait",
    "fetching",
    "spinner",
    "skeleton",
)


@dataclass(frozen=True)
class ShellVerdict:
    """The classifier's decision, with the signals that produced it.

    ``needs_more_than_static`` is the actionable form of ``is_shell``. It means a
    plain HTTP read was not sufficient for *some* reason - a client-side
    application, or a document that carried nothing at all - and it maps to
    ``SOURCE_REQUIRES_RENDERING``. That state is deliberately about the read
    rather than about JavaScript specifically, because an empty response is just
    as inconclusive as a rendered one and must not become a negative either.
    """

    is_shell: bool
    text_ratio: float
    script_ratio: float
    empty_app_container: bool
    has_hydration_marker: bool
    has_bundle_marker: bool
    has_loading_marker: bool
    signals: tuple[str, ...] = field(default_factory=tuple)
    #: True when the document returned nothing a reader could ever see, so no
    #: amount of waiting on this response would help and absence is unproven.
    empty_document: bool = False

    @property
    def reason(self) -> str:
        return ", ".join(self.signals) if self.signals else "no shell signals"

    @property
    def needs_more_than_static(self) -> bool:
        return self.is_shell or self.empty_document


def _script_bytes(html: str) -> int:
    return sum(len(match.group(0)) for match in re.finditer(r"(?is)<script\b.*?</script>", html))


def _visible_text(html: str) -> str:
    """Return the document's visible text, excluding script and style bodies.

    Script text is not visible to a reader, so counting it would make every
    script-heavy page look content-rich, which is the failure mode that made the
    single-signal version wrong.
    """
    stripped = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    stripped = re.sub(r"(?is)<style\b.*?</style>", " ", stripped)
    stripped = re.sub(r"(?is)<!--.*?-->", " ", stripped)
    stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _empty_app_container(html: str) -> bool:
    """Return whether a framework root element is present and has no text."""
    for container_id in APP_CONTAINER_IDS:
        match = re.search(
            rf'(?is)<(\w+)[^>]*\bid=["\']{re.escape(container_id)}["\'][^>]*>(.*?)</\1>',
            html,
        )
        if match is None:
            continue
        inner = re.sub(r"(?is)<script\b.*?</script>", " ", match.group(2))
        inner = re.sub(r"(?s)<[^>]+>", " ", inner)
        if not inner.strip():
            return True
    return False


def _anchors_naming_an_academic(html: str) -> int:
    """Count personal-profile links whose text actually names an academic.

    Counting links under ``/people/`` is not enough: a directory's own
    navigation contributes some, and on the real Adelaide directory every
    ``/people/`` link pointed at the directory rather than at a person. What
    distinguishes a person link is that its text states an academic role, so that
    is what is counted - using the one central role vocabulary, so this module
    cannot disagree with the rest of the pipeline about who counts.
    """
    from .supervisor_person import academic_role_in

    count = 0
    for match in re.finditer(
        r'(?is)<a\b[^>]*>(.*?)</a>', html
    ):
        href_match = re.search(r'(?is)href=["\']([^"\']*)["\']', match.group(0))
        if href_match is None:
            continue
        href = href_match.group(1).lower()
        if not any(root in href for root in ("/people/", "/person/", "/profile", "/staff/")):
            continue
        text = re.sub(r"(?s)<[^>]+>", " ", match.group(1))
        if academic_role_in(text):
            count += 1
    return count


def classify_shell(html: str) -> ShellVerdict:
    """Return whether ``html`` is a client-side shell, and why."""
    html = html or ""
    if not html:
        return ShellVerdict(
            False, 0.0, 0.0, False, False, False, False, ("empty_document",), True
        )

    total = len(html)
    text = _visible_text(html)
    text_ratio = len(text) / max(1, total)
    script_ratio = _script_bytes(html) / max(1, total)

    empty_container = _empty_app_container(html)
    hydration = any(marker in html for marker in HYDRATION_MARKERS)
    bundle = any(marker in html for marker in BUNDLE_MARKERS)
    loading = any(marker in text.lower()[:600] for marker in LOADING_MARKERS)

    signals: list[str] = []
    if text_ratio < SPARSE_TEXT_RATIO:
        signals.append(f"sparse_text({text_ratio:.3f})")
    if empty_container:
        signals.append("empty_app_container")
    if hydration:
        signals.append("hydration_state")
    if bundle:
        signals.append("client_bundle")
    if script_ratio > SCRIPT_HEAVY_RATIO:
        signals.append(f"script_heavy({script_ratio:.3f})")

    # A document with no visible text, no links and no controls returned nothing
    # a reader could ever see. Whatever produced it, a negative claim would be
    # unfounded, so it counts as "a static read was not enough".
    empty_document = (
        not text
        and "<a" not in html.lower()
        and "<form" not in html.lower()
        and "<input" not in html.lower()
        and script_ratio < SCRIPT_HEAVY_RATIO
    )

    # A page that presents itself as a people directory, carries almost no
    # readable text, and publishes not one personal-profile link is telling us
    # nothing about who works there.
    #
    # This signal exists because of a real institution. Adelaide's directory
    # measured a 0.039 text ratio with no `id="app"` container and an inline
    # script share below the heavy threshold, so every other signal abstained and
    # the page was classified as statically readable. That would have recorded a
    # negative for a university whose staff list the crawler simply never saw.
    #
    # The distinction being enforced is narrow: "we found nobody here" is not the
    # same claim as "this page showed us everybody who works here". A directory
    # with entries, or with enough prose to explain itself, is unaffected.
    person_link_count = _anchors_naming_an_academic(html)
    directory_without_entries = (
        looks_like_directory_listing(html)
        and person_link_count == 0
        and text_ratio < SPARSE_TEXT_RATIO
    )
    if directory_without_entries:
        signals.append("directory_without_entries")

    # An empty framework root is sufficient on its own. `div#app`,
    # `div#__next`, `div#__nuxt` exist precisely so a client framework can mount
    # into them; if the server left one empty, the server rendered nothing into
    # the content area, which is the definition of a shell. Requiring
    # corroboration here would miss the clearest case while every weaker signal
    # still has to agree with at least one other before it counts.
    if empty_container:
        signals.insert(0, "empty_app_container")

    is_shell = bool(empty_container) or len(signals) >= 2

    return ShellVerdict(
        is_shell=is_shell,
        text_ratio=text_ratio,
        script_ratio=script_ratio,
        empty_app_container=empty_container,
        has_hydration_marker=hydration,
        has_bundle_marker=bundle,
        has_loading_marker=loading,
        signals=tuple(signals),
        empty_document=empty_document,
    )


def looks_like_directory_listing(html: str) -> bool:
    """Return whether a page presents itself as a people directory.

    Used to justify the *structural* person signal: a person-shaped link only
    carries weight when the page around it is a directory. This is what stops a
    page's navigation from supplying "people" context.
    """
    text = _visible_text(html or "").lower()[:2000]
    markers = ("faculty", "staff", "academic staff", "our people", "directory", "people")
    return any(marker in text for marker in markers)


def render_href_allowed(url: str, seed_host: str, allowed_suffixes: tuple[str, ...]) -> bool:
    """Return whether the browser may follow ``url`` from ``seed_host``.

    The one-domain boundary, enforced before a navigation rather than after it.
    Rejecting a third-party profile link *before* fetching it is the difference
    between a bounded institutional crawl and a crawler that wanders.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.netloc or "").lower()
    if not host:
        return False

    seed = (seed_host or "").lower()
    if not seed:
        return False
    if host == seed or host.endswith("." + seed):
        return True

    # A sibling subdomain of the same registrable academic domain is still the
    # institution. Reuses the proven registrable-domain rule rather than
    # inventing a second one here.
    from .supervisor_discovery import same_institution

    return same_institution(host, seed) and host.endswith(allowed_suffixes)


__all__ = [
    "APP_CONTAINER_IDS",
    "ShellVerdict",
    "classify_shell",
    "looks_like_directory_listing",
    "render_href_allowed",
]