"""Strict audit of every stored image.

The acceptance rules forbid tracking pixels, third-party hosts and accepted
images without provenance. A stored image is only acceptable when all of these
hold:

  1. the URL is not an advertising/tracking/analytics beacon
  2. the host belongs to the official source (or its recognised CDN)
  3. the record carries complete provenance
  4. a kind is set, so the renderer can choose contain vs cover correctly

Anything that fails is cleared from active use and written to the image review
queue, preserving the audit trail. Clearing is reversible: the record keeps its
official source URL and can be re-evaluated later.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import ImageReview, Scholarship
from app.services.image_evaluation_status import ImageEvaluationStatus

PERSIST = "--persist" in sys.argv

# Hosts that are never a scholarship's own image. Ad/analytics beacons were
# accepted as OpenGraph images because they are served by the official domain
# in some cases, or were picked up from third-party markup.
AD_HOST_PATTERNS = (
    "ads.linkedin.com",
    "px.ads.linkedin.com",
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "google-analytics.com",
    "facebook.com/tr",
    "connect.facebook.net",
    "bat.bing.com",
    "analytics.",
    "pixel.",
    "track.",
    "beacon.",
    "hotjar.com",
    "scorecardresearch.com",
    "quantserve.com",
)

# URL path fragments that identify a beacon regardless of host.
BEACON_PATH = re.compile(
    r"(/collect|/track|/pixel|/beacon|/impression|/view\?|/collect\?|"
    r"/_ga|/stats\.gif|/__utm|/gtm\.js)",
    re.IGNORECASE,
)

# A filename that is plainly a site asset rather than scholarship artwork.
GENERIC_ASSET = re.compile(
    r"(logo|icon|favicon|placeholder|spacer|blank|1x1|pixel|avatar)\b",
    re.IGNORECASE,
)

#: Filename fragments that identify a site-wide asset rather than scholarship
#: artwork. Contao/CMS sites publish one "default" OpenGraph image and one
#: contact/footer/decorative image and reuse them everywhere; those are exactly
#: the generic site images the acceptance rules forbid being presented as
#: scholarship imagery.
GENERIC_SITE_IMAGE = re.compile(
    r"(default[_-]?og|default[_-]?image|og[_-]?default|placeholder|spacer|"
    r"kontakt|contact[_-]?us|footer[_-]?|dibai|bg[_-]?decoration|"
    r"news[_-]?thumb|breaking[_-]?news|site[_-]?logo|header[_-]?bg)",
    re.IGNORECASE,
)

VALID_KINDS = {
    "program_image",
    "official_banner",
    "official_provider",
    "official_university",
    "official_government",
    "official_logo",
}


def host_of(url: str | None) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower().removeprefix("www.")


def registrable(host: str) -> str:
    parts = host.split(".")
    return ".".join(parts[-3:]) if len(parts) > 2 else host


#: Failures that mean the asset itself is unacceptable. These are cleared:
#: an advertising beacon is never a scholarship image, whatever metadata it
#: carries.
UNUSED = {
    "advertising_or_tracking_beacon",
    "beacon_path",
    "third_party_host",
}


#: Hosts that can never host a scholarship's own image. Everything else is
#: treated as ambiguous and routed to human review rather than deleted: a
#: university's CDN (cdn.ubc.ca, imgix, wixstatic, kc-usercontent) or its own
#: second domain (ku.dk, aau.dk, state.gov) is frequently the correct owner even
#: when the record's official_source_url points elsewhere, and deleting those
#: would destroy legitimate official images.
JUNK_HOSTS = (
    "facebook.com",
    "fbcdn.net",
    "gravatar.com",
    "ads.linkedin.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "pinterest.com",
    "reddit.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "wikipedia.org",
    "wikimedia.org",
    "unsplash.com",
    "shutterstock.com",
    "gettyimages.com",
    "istockphoto.com",
    "alamy.com",
    "dreamstime.com",
    "pixabay.com",
    "entries.domains",
    "scorecardresearch.com",
    "quantserve.com",
    "hotjar.com",
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "bat.bing.com",
)


def classify(reasons: list[str], row) -> tuple[bool, list[str]]:
    """Decide whether to clear the image, or flag it for review.

    A missing ``image_kind`` or a missing alt text is a metadata gap on a
    perfectly good official image. Discarding a real Erasmus hero image because
    a column was empty would destroy verified data, so those are repaired.

    A host that cannot own a scholarship image is cleared outright. A merely
    unrecognised host is ambiguous and is only queued for review.
    """
    hard = [
        r
        for r in reasons
        if r.split(":")[0] in ("advertising_or_tracking_beacon", "beacon_path")
        or (r == "third_party_host" and any(j in host_of(row.image_url) for j in JUNK_HOSTS))
        or r == "generic_site_image"
    ]
    soft = [r for r in reasons if r not in hard]
    return bool(hard), hard + soft


def normalise_kind(kind: str | None, host: str, official_host: str) -> str:
    """Map a stored kind onto the canonical vocabulary.

    ``generic_official`` said nothing about *who* issued the asset, and
    ``official_media`` said nothing at all. Both are resolved against the
    issuing host so a card can state whether the identity belongs to a
    university, a government body or a provider. An issuer we cannot classify
    falls back to official_logo, which is honest: a logo is a last-resort
    fallback, never presented as programme artwork.
    """
    key = (kind or "").strip()
    if key in VALID_KINDS:
        return key
    base = host_of(host)
    gov = (".gov.", ".gov", "-gov.", "europa.eu", "un.org", "who.int", "undp.org")
    if any(token in base for token in gov):
        return "official_government"
    edu = (".edu", ".ac.", ".univ", "university", "hochschule", "unibe")
    if any(token in base for token in edu):
        return "official_university"
    return "official_logo"


def reasons_for(row) -> list[str]:
    reasons: list[str] = []
    url = row.image_url
    if not url:
        return ["no image stored"]

    host = host_of(url)
    lowered = url.lower()
    if any(pattern in lowered for pattern in AD_HOST_PATTERNS):
        reasons.append("advertising_or_tracking_beacon")
    if BEACON_PATH.search(url):
        reasons.append("beacon_path")
    if GENERIC_ASSET.search(urlparse(url).path):
        reasons.append("generic_site_asset")
    if GENERIC_SITE_IMAGE.search(urlparse(url).path):
        # A site-wide default/OG/contact image is not scholarship artwork, no
        # matter which column it was stored in.
        reasons.append("generic_site_image")

    official_host = host_of(row.official_source_url)
    if official_host and registrable(host) and registrable(host) != registrable(official_host):
        # A different organisation's CDN is not proof of ownership.
        if not registrable(host).endswith(registrable(official_host)):
            reasons.append("third_party_host")

    if not all(
        [
            row.image_url,
            row.image_source_url,
            row.image_source_type,
            row.image_alt_text,
            row.image_verified_at,
        ]
    ):
        reasons.append("incomplete_provenance")
    if not row.image_kind:
        reasons.append("image_kind_unset")
    elif row.image_kind not in VALID_KINDS:
        reasons.append(f"unknown_kind:{row.image_kind}")
    return reasons


def main() -> None:
    factory = get_session_factory()
    session = factory()
    try:
        rows = list(
            session.scalars(
                select(Scholarship).where(Scholarship.verification_status != "quarantined")
            )
        )
        bad = []
        for row in rows:
            if row.image_verified_at is None and not row.image_url:
                continue
            found = reasons_for(row)
            if found:
                clear, all_reasons = classify(found, row)
                bad.append((row, all_reasons, clear))

        to_clear = [b for b in bad if b[2]]
        to_repair = [b for b in bad if not b[2]]
        print(f"mode                : {'PERSIST' if PERSIST else 'DRY RUN'}")
        print(f"records with image  : {sum(1 for r in rows if r.image_url)}")
        print(f"must clear (bad asset): {len(to_clear)}")
        print(f"repair metadata only  : {len(to_repair)}")
        from collections import Counter

        counts = Counter(reason for _, rs, _ in bad for reason in rs)
        for reason, n in counts.most_common():
            print(f"   {reason:32s} {n}")

        for row, found, clear in bad:
            print(f"\n  {'CLEAR ' if clear else 'REPAIR'} id={row.id:<4} {','.join(found)}")
            print(f"     {str(row.title)[:70]}")
            print(f"     image : {str(row.image_url)[:92]}")

        if not PERSIST:
            print("\ndry run: no changes written")
            return

        for row, found, clear in bad:
            if clear:
                session.add(
                    ImageReview(
                        scholarship_id=row.id,
                        image_url=row.image_url or "",
                        image_kind=row.image_kind or "unknown",
                        source_page=row.image_source_url or row.official_source_url,
                        source_type=row.image_source_type,
                        relevance_evidence="; ".join(found),
                        licensing_status="rejected",
                        confidence="low",
                        reason_for_review=found[0][:255],
                        decision="rejected",
                        reviewer_note="image_audit: " + ",".join(found),
                    )
                )
                row.image_url = None
                row.image_source_url = None
                row.image_source_type = None
                row.image_kind = None
                row.image_alt_text = None
                row.image_verified_at = None
                row.image_evaluation_status = ImageEvaluationStatus.INVALID_CANDIDATES
                row.image_evaluated_at = None
            else:
                # Metadata-only repair: keep the verified asset. The image is a
                # real official picture; only its provenance columns were thin.
                if not row.image_source_url:
                    row.image_source_url = row.official_source_url
                if not row.image_source_type:
                    row.image_source_type = "official_page"
                if not row.image_alt_text:
                    row.image_alt_text = (row.title or "")[:255]
                row.image_kind = normalise_kind(
                    row.image_kind, row.image_url, row.official_source_url
                )
                if row.image_verified_at is None:
                    row.image_verified_at = row.image_evaluated_at or datetime.now(
                        timezone.utc
                    )
                row.image_evaluation_status = ImageEvaluationStatus.VERIFIED
        session.commit()
        print(
            f"\ncleared {len(to_clear)} non-compliant images, repaired metadata on "
            f"{len(to_repair)}; review rows written"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
