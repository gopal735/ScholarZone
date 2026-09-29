"""Pre-insert quality gate for newly discovered candidates.

Discovery once created a scholarship straight from a scraped candidate, with
``is_verified=True`` and ``"Unknown"`` standing in for whatever the scraper had
not read. The catalogue consequently grew entries such as::

    id 490  "Ministry of Education (MOE)"   https://moe.gov.sg/
    id 491  "Home - Erasmus+"                https://erasmus-plus.ec.europa.eu/

Both are site landing pages. Both were published as verified scholarships, and
both had to be found and removed by hand afterwards.

The lesson is not that the scraper needs a stricter list of required fields.
A programme with a thin official page is still a real programme, and a rule
that demanded twenty populated fields would reject the long tail of genuine
scholarships while still admitting any page that happened to pad itself with
text. What separates the two examples above from a real programme is not field
count - it is that a real programme is *about a programme*: it has an
identifier, a source that is a programme page rather than a site root, and
scholarship-specific content.

So the gate is built from three independent families of signal and requires
agreement, not a threshold:

* **structural** - is the source a programme page or a site root?
* **identity** - does the title read like a programme, or like a site?
* **evidential** - is there scholarship-specific content at all?

A record must clear the structural and identity checks and must present real
evidence. Anything short of that does not become a public verified
scholarship; it is routed to review, where a human decides. That ordering is
deliberate: quarantine must never be the first line of defence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class DiscoveryVerdict(str, Enum):
    """What to do with a candidate before it becomes a public record."""

    ACCEPT = "accept"
    # Plausibly a real programme but the evidence is thin. Not published.
    REVIEW = "review"
    # Structurally not a scholarship page. Not published, ever, automatically.
    REJECT = "reject"


@dataclass
class QualityVerdict:
    verdict: DiscoveryVerdict
    reasons: list[str] = field(default_factory=list)
    evidence_score: int = 0

    @property
    def accepted(self) -> bool:
        return self.verdict is DiscoveryVerdict.ACCEPT

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "evidence_score": self.evidence_score,
        }


# Titles that identify a page's role in a site rather than a programme.
#
# Matched against the WHOLE title, not a prefix. "Home Economics Scholarship" is
# a degree, not a landing page, and an unanchored rule rejected it - which is
# exactly the kind of over-strict gate that destroys a catalogue's long tail.
_LANDING_TITLE_EXACT = re.compile(
    r"^\s*(home|homepage|welcome|about(\s+us)?|admissions?|apply|application|"
    r"contact(\s+us)?|search|news|events|blog|faq|faqs|help|support|"
    r"site\s*map|privacy\s*policy|terms(\s+(and|&)\s+conditions)?|"
    r"cookie\s*policy|log\s*in|login|sign\s*in|signin|register|"
    r"sign\s*up|signup|my\s+account|account|dashboard)\s*[.!]?\s*$",
    re.IGNORECASE,
)

# A site name prefixed onto a brand, e.g. "Home - Erasmus+", "Welcome to X".
# These are only landing pages when the separator is present; without it the
# words are ordinary title material.
_LANDING_TITLE_BRANDED = re.compile(
    r"^\s*(home|homepage|welcome\s+to|welcome)\s*[-–—|:]\s*\S",
    re.IGNORECASE,
)

# A bare section heading, e.g. "Scholarships" or "Programmes", with no
# qualifier. A real scheme always has something after the noun.
_LANDING_TITLE_BARE = re.compile(
    r"^\s*(scholarships?|programmes?|programs?|courses?|degrees?|"
    r"financial\s+aid|how\s+to\s+apply)\s*(\||[-–—|:])?\s*$",
    re.IGNORECASE,
)

# Words that make a title a *scheme* rather than an organisation. Checked
# before the organisation rule, because "University of Miami Stamps
# Scholarship" is a scholarship and "University of Miami" is a university, and
# the difference is the noun at the end.
_SCHEME_WORD = re.compile(
    r"\b(scholarships?|fellowships?|programmes?|programs?|grants?|awards?|"
    r"bursaries?|bursaries|studentships?|traineeships?|exchange|exchanges|"
    r"fund|funding|prizes?|medals?|studentship|apprenticeships?)\b",
    re.IGNORECASE,
)

# Institution words that on their own describe an organisation, not a scheme.
# Tolerates the usual suffixes: "Ministry of Education", "University of Oxford",
# "British Council (BC)". Requires the title to be short enough to be a
# department heading - "Ministry of Education International Scholarship Fund" is
# a scheme and must survive.
_ORGANISATION_TITLE = re.compile(
    r"^\s*(ministry|department|university|college|school|institute|academy|"
    r"foundation|agency|commission|council|authority|government|embassy|"
    r"consulate)\b"
    r"(\s+(of|for|on|and|de)\s+[\w\s]{0,40}?)?"
    r"(\s*\(([\w.\s]{1,20})\))?"
    r"\s*[.!]?\s*$",
    re.IGNORECASE,
)

_BARE_ROOT = re.compile(r"^https?://(www\.)?[^/]+/?$")

# Paths that are a site's own furniture rather than a programme page.
#
# Must END at the section word. "/about" is a department page, but
# "/news/call-for-visiting-fellowships-2026" is a specific announcement about a
# real fellowship, and treating a news post as furniture would reject genuine
# opportunities. Only the bare section is furniture.
_NON_PROGRAMME_PATH = re.compile(
    r"^/(home|index|welcome|about|about-us|contact|search|news|events|blog|"
    r"privacy|terms|cookies?|sitemap|login|signin|sign-in|register|account|"
    r"help|faq|faqs)/?$",
    re.IGNORECASE,
)

# Fields that carry scholarship-specific meaning. A programme with several of
# these populated is describing a scheme; a landing page has none of them.
_EVIDENCE_FIELDS = (
    "description", "deadline", "deadline_date", "eligibility", "eligibility_summary",
    "requirements", "benefits", "coverage", "documents", "application_url",
    "application_method", "selection_notes", "duration", "application_period",
    "program_type", "best_fit", "notes", "catalogue_url", "official_updates_url",
)

# Values that mean "the scraper did not read this", not "the programme says so".
_PLACEHOLDERS = frozenset({"", "unknown", "n/a", "na", "none", "not specified", "null", "-"})

# Artifacts left behind by an HTML-aware but badly written scraper.
#
# These show up in real extracted values, not in theory. A live discovery round
# produced `degree="Programmes[/LINK]"` from a page whose markup used
# unstripped BC-style link tags. A value containing markup is never a fact about
# a scholarship, so its presence discredits the extraction rather than counting
# as evidence.
_HTML_ARTIFACT = re.compile(r"\[/?[A-Z]{1,6}\]|<[a-z/][^>]*>|&nbsp;|&amp;|&lt;|&gt;|&quot;", re.IGNORECASE)

# Fields that must be short, human-readable labels rather than prose.
#
# `degree` is the field that failed hardest: it received whole marketing
# sentences ("programmes from more than 77 esteemed institutions. Do you want to
# take courses taught in English? At"). A degree level is a short label, so a
# long value is evidence the extractor grabbed body copy instead of the field.
_SHORT_FIELD_LIMIT = 60

_LABEL_FIELDS = ("degree", "funding", "status", "program_type", "best_fit", "duration")

# Degree-level vocabulary. Used as a *soft* signal: a missing word is not
# disqualifying on its own, because official pages say "undergraduate" or
# "3-year course" as readily as "Bachelor's", but a long value containing no
# degree word at all is a sentence, not a level.
_DEGREE_WORD = re.compile(
    r"\b(bachelor|master|mba|msc|ma\b|ms\b|phd|ph\.d|doctor|postdoc|"
    r"post-?doctoral|undergraduate|graduate|diploma|certificate|course|courses|"
    r"degree|degrees|licence|license|associate|foundation year|phd programme)\b",
    re.IGNORECASE,
)

# Titles that describe a *function on the site* rather than a programme.
#
# These are the "serial numbers filed off" landing pages: the page genuinely
# contains scholarship words, so field counting passes them, and the title is
# the only thing that says what they actually are. "Find your programme" is a
# search box over a catalogue of other people's programmes, not a programme.
_TITLE_ROLE = re.compile(
    r"^\s*(find|search|browse|explore|discover|look\s+for|view|view\s+all|"
    r"all|list|listing|compare|check)\b.{0,40}?"
    r"(programmes?|programs?|scholarships?|fellowships?|courses?|"
    r"opportunities|grants?|degrees?)\b",
    re.IGNORECASE,
)

# Page-role words in a title that mark a page about *how to apply* rather than
# about a scheme. A real programme is about the programme; these are about the
# process around it, and several of them are per-scheme process pages that
# belong to a record, not to a record of their own.
_TITLE_PROCESS = re.compile(
    r"\b(application\s+timeline|application\s+timeline|how\s+to\s+apply|"
    r"application\s+process|application\s+procedure|application\s+guidelines?|"
    r"eligibility\s+criteria|selection\s+process|faq|faqs|contact|"
    r"documents?\s+required|required\s+documents)\b",
    re.IGNORECASE,
)

# CMS/portal furniture inside a path. `.html` on a scholarship URL is a template
# artefact of a site that never moved to clean URLs; combined with a `/menu/`
# segment it is a navigation page. Modern programme pages are extensionless.
_FURNITURE_PATH_SEGMENT = re.compile(r"/(menu|navigation|navbar|breadcrumb|site-map)/", re.IGNORECASE)
_TEMPLATE_FILE_EXTENSION = re.compile(r"\.(html?|asp|aspx|jsp|php|cgi)$", re.IGNORECASE)


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return str(value).strip().lower() in _PLACEHOLDERS


def _populated(fields: dict[str, Any]) -> int:
    return sum(1 for name in _EVIDENCE_FIELDS if not _is_placeholder(fields.get(name)))


def _has_html_artifact(fields: dict[str, Any]) -> list[str]:
    """Names of populated fields whose value still contains markup.

    Such a value is not weak evidence, it is corrupt evidence, so it is reported
    separately and never counted towards the score.
    """
    dirty: list[str] = []
    for name, value in fields.items():
        if _is_placeholder(value):
            continue
        if isinstance(value, (list, tuple, set)):
            parts = [str(v) for v in value]
        elif isinstance(value, dict):
            parts = [f"{k}: {v}" for k, v in value.items()]
        else:
            parts = [str(value)]
        if any(_HTML_ARTIFACT.search(part) for part in parts):
            dirty.append(name)
    return dirty


def _prose_labels(fields: dict[str, Any]) -> list[str]:
    """Short-label fields that instead received a sentence.

    Catches the extractor writing body copy into a field that is supposed to
    hold a label, which is how `degree` became a 120-character marketing
    sentence in a live round.
    """
    offenders: list[str] = []
    for name in _LABEL_FIELDS:
        value = fields.get(name)
        if _is_placeholder(value):
            continue
        text = str(value).strip()
        if len(text) > _SHORT_FIELD_LIMIT:
            offenders.append(name)
        elif name == "degree" and not _DEGREE_WORD.search(text):
            offenders.append(name)
    return offenders


def evidence_score(fields: dict[str, Any]) -> int:
    """How much scholarship-specific content the candidate carries.

    Reported rather than only used, so a rejected candidate can say *why* it
    looked empty instead of simply failing.
    """
    return _populated(fields)


def assess_candidate(
    title: str | None,
    url: str | None,
    fields: dict[str, Any] | None = None,
) -> QualityVerdict:
    """Decide whether a discovered candidate may become a public record."""
    fields = fields or {}
    reasons: list[str] = []
    score = _populated(fields)

    clean_title = (title or "").strip()
    parsed = urlparse(url) if url else None
    host = (parsed.netloc or "").lower().removeprefix("www.") if parsed else ""

    # -- structural -------------------------------------------------
    # Recorded as a *concern*, not a verdict.
    #
    # A bare site root is genuinely weak evidence - it may be a landing page -
    # but it is not proof. Measured against the live catalogue, rejecting on
    # this rule alone would have refused 67 of 487 real scholarships including
    # Erasmus Mundus, DAAD, Fulbright and Global Korea Scholarship, whose
    # official entry point is legitimately the programme's own domain root. The
    # same domain also hosts the "Home - Erasmus+" landing page, so the URL
    # cannot tell the two apart. Title and evidence can.
    structural = False
    bare_root = bool(url) and bool(_BARE_ROOT.match(url.strip()))
    if bare_root:
        reasons.append(f"official source is a bare site root, not a programme page: {url}")
        structural = True
    path = parsed.path if parsed else ""
    furniture_path = bool(path and _NON_PROGRAMME_PATH.match(path))
    if furniture_path:
        reasons.append(f"official source path is site furniture, not a programme page: {path}")
        structural = True
    # A navigation segment is decisive rather than a hint, for the same reason
    # a bare furniture path is: `/menu/...` is the site's own link structure, and
    # a page reached through it is a page *about* navigating, whatever it
    # happens to contain. Scored softly, a menu page with three populated fields
    # sailed through - which is exactly how "Study in Hungary - Application
    # Timeline" reached production.
    navigation_path = bool(path and _FURNITURE_PATH_SEGMENT.search(path))
    if navigation_path:
        reasons.append(
            f"official source path is site navigation, not a programme page: {path}"
        )
        structural = True
    if path and _TEMPLATE_FILE_EXTENSION.search(path):
        reasons.append(
            f"official source path ends in a template file extension, "
            f"typical of a navigation page: {path}"
        )
        structural = True
    if not url:
        reasons.append("no official source url")

    # -- integrity of the extracted values ---------------------------
    # Checked before the identity and evidence logic, because a corrupt
    # extraction makes every downstream judgement unreliable: it inflates the
    # evidence score with markup and it fills a short-label field with prose.
    dirty = _has_html_artifact(fields)
    if dirty:
        reasons.append(
            "extracted values still contain HTML markup, so the extraction is "
            f"unreliable: {', '.join(sorted(dirty)[:5])}"
        )
    prose = _prose_labels(fields)
    if prose:
        reasons.append(
            "short-label fields contain prose rather than a label: "
            f"{', '.join(sorted(prose)[:5])}"
        )

    # -- identity ---------------------------------------------------
    identity_bad = False
    if not clean_title:
        reasons.append("no title")
        identity_bad = True
    elif (
        _LANDING_TITLE_EXACT.match(clean_title)
        or _LANDING_TITLE_BRANDED.match(clean_title)
        or _LANDING_TITLE_BARE.match(clean_title)
    ):
        reasons.append(f"title reads as a site landing page, not a programme: {clean_title!r}")
        identity_bad = True
    elif _TITLE_ROLE.match(clean_title):
        reasons.append(
            f"title describes a search or listing over programmes, not a programme: "
            f"{clean_title!r}"
        )
        identity_bad = True
    elif _TITLE_PROCESS.search(clean_title) and not _SCHEME_WORD.search(clean_title):
        reasons.append(
            f"title describes the application process, not a scheme: {clean_title!r}"
        )
        identity_bad = True
    elif _ORGANISATION_TITLE.match(clean_title) and not _SCHEME_WORD.search(clean_title):
        # An organisation heading, not a scheme. A title that goes on to name a
        # scholarship, fellowship or grant is a scheme however it starts.
        reasons.append(f"title names an organisation, not a scheme: {clean_title!r}")
        identity_bad = True

    # -- provider ----------------------------------------------------
    # A record with no awarding body is not a scholarship record. This is the
    # single check that would have caught both records a live deep round
    # inserted: both had `official_source=None` and were published as verified
    # anyway, because field counting never asked who was offering them.
    provider = fields.get("provider") or fields.get("official_source")
    provider_missing = _is_placeholder(provider)
    if provider_missing:
        reasons.append("no provider or awarding body could be identified")

    # -- decision ---------------------------------------------------
    # A title that names a site, a page role, or an organisation is decisive on
    # its own: no amount of scraped text makes "Home - Erasmus+" a scheme.
    if identity_bad:
        return QualityVerdict(DiscoveryVerdict.REJECT, reasons, score)

    # A corrupt extraction is decisive too. Markup in a field, or a sentence in
    # a label field, means the scraper lost track of the page, and a candidate
    # that cannot be read reliably must not be published automatically.
    if dirty or prose:
        return QualityVerdict(DiscoveryVerdict.REJECT, reasons, score)

    # Site-furniture paths, navigation paths and a missing URL are equally
    # unambiguous. None of them becomes a scholarship, however much text the
    # page happens to contain.
    if not url or furniture_path or navigation_path:
        return QualityVerdict(DiscoveryVerdict.REJECT, reasons, score)

    # No awarding body: not publishable, and not a judgement call a human can
    # make from the scraped text either. Sent to review rather than rejected so
    # the candidate is still visible.
    if provider_missing:
        return QualityVerdict(DiscoveryVerdict.REVIEW, reasons, score)

    # A bare root with no scholarship-specific content behind it is a landing
    # page with the serial numbers filed off.
    if structural and score < 2:
        return QualityVerdict(DiscoveryVerdict.REJECT, reasons, score)

    # Enough evidence and a real programme title: accept, even on a root URL.
    if score >= 2:
        return QualityVerdict(DiscoveryVerdict.ACCEPT, reasons, score)

    # Otherwise a human decides. Never published automatically.
    return QualityVerdict(DiscoveryVerdict.REVIEW, reasons, score)
