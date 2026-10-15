"""Discover and verify official logos for the new top-country records."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

LIVE_DIR = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live_upcoming")
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 30

LOGO_HINT = re.compile(r"logo|brand|emblem|seal", re.I)


def registrable_domain(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def clean_text(soup):
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))


def extract_logos(soup, base_url, page_domain):
    out, seen = [], set()

    def add(u, kind, alt, score):
        if not u or u.startswith("data:") or u.startswith("javascript:"):
            return
        abs_url = urljoin(base_url, u)
        if not abs_url.startswith("http"):
            return
        cand_dom = registrable_domain(abs_url)
        if not cand_dom or not (cand_dom == page_domain or cand_dom.endswith("." + page_domain) or page_domain.endswith("." + cand_dom)):
            return
        if abs_url in seen:
            return
        seen.add(abs_url)
        out.append({"url": abs_url, "kind": kind, "alt": alt, "score": score})

    for link in soup.find_all("link", rel=True):
        rel = " ".join(link.get("rel", [])).lower()
        href = link.get("href")
        if href and "icon" in rel and "mask" not in rel:
            add(href, "link_icon", link.get("aria-label"), 60 if "apple-touch" in rel else 70)
    for meta in soup.find_all("meta", property=lambda v: v and v.lower() == "og:image"):
        add(meta.get("content"), "og_image", None, 50)
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        hay = f"{src} {img.get('alt') or ''} {' '.join(img.get('class', []))} {img.get('id') or ''}".lower()
        score = 0
        if LOGO_HINT.search(hay):
            score = 90
        elif "logo" in src.lower():
            score = 85
        if score > 0:
            add(src, "img_logo", img.get("alt") or None, score)
    out.sort(key=lambda c: -c["score"])
    return out


def verify_image(url: str) -> bool:
    try:
        g = requests.get(url, headers=UA, timeout=20, stream=True, allow_redirects=True)
        ok = g.status_code == 200 and g.headers.get("Content-Type", "").startswith("image/")
        g.close()
        return ok
    except Exception:
        return False


def find_logo(rec: dict) -> dict | None:
    urls = []
    for key in ("official_source_url", "application_link", "catalogue_url", "official_updates_url"):
        u = rec.get(key)
        if u and u.startswith("http"):
            urls.append(u)
    if not urls:
        return None
    candidates = []
    for u in urls[:2]:
        try:
            r = requests.get(u, headers=UA, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for c in extract_logos(soup, r.url, registrable_domain(r.url)):
                c["from_page"] = r.url
                candidates.append(c)
        except Exception:
            continue
    dedup = {}
    for c in candidates:
        if c["url"] not in dedup or c["score"] > dedup[c["url"]]["score"]:
            dedup[c["url"]] = c
    ranked = sorted(dedup.values(), key=lambda c: -c["score"])
    for c in ranked[:8]:
        if verify_image(c["url"]):
            return {
                "logo_url": c["url"],
                "logo_source_url": c.get("from_page") or urls[0],
                "logo_alt": c.get("alt") or rec.get("official_source"),
            }
    return None


def main() -> int:
    rec_file = LIVE_DIR / "research_agent_top_countries.json"
    recs = json.loads(rec_file.read_text(encoding="utf-8"))
    print(f"Loaded {len(recs)} records")
    for rec in recs:
        logo = find_logo(rec)
        rec["logo"] = logo
        if logo:
            print(f"  OK   {rec['title'][:55]:55s} -> {logo['logo_url'][:80]}")
        else:
            print(f"  NONE {rec['title'][:55]:55s} -> no verified official logo")
    rec_file.write_text(json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    with_logo = sum(1 for r in recs if r.get("logo"))
    print(f"\n{with_logo}/{len(recs)} records have verified official logos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
