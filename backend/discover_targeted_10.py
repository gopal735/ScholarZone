"""Targeted image discovery for 10 specific scholarships.

Tries the suggested official URLs for each ID, extracts og:image, twitter:image,
JSON-LD images, and main content <img> tags. Filters out UI/logo/icon assets.
Does NOT write to the database. Saves results to JSON.
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend')
from app.database import get_engine, init_database
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.models import Scholarship

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
ALT_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

OUT = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_targeted.json')

# Map of scholarship_id -> list of URLs to try
TARGETS = {
    26: [
        "https://www.studyinkorea.go.kr/en/main.do",
        "https://www.studyinkorea.go.kr",
        "https://www.niied.go.kr/eng/index.do",
        "https://www.niied.go.kr",
    ],
    28: [
        "https://www.chevening.org/scholarships/",
        "https://www.chevening.org/scholarships/who-can-apply/",
        "https://www.chevening.org",
    ],
    30: [
        "https://australiaawards.com.au",
        "https://australiaawards.com.au/en/study-applications",
        "https://www.dfat.gov.au/people-to-people/australia-awards",
        "https://www.dfat.gov.au/people-to-people/australia-awards-scholarships",
    ],
    31: [
        "https://www.studyinnl.org/finances/nl-scholarship",
        "https://www.studyinnl.org",
        "https://www.nuffic.nl/en/subjects/information-for-students/scholarships",
        "https://www.nuffic.nl",
    ],
    32: [
        "https://si.se/en/apply/scholarships/",
        "https://si.se/en/apply/scholarships/swedish-institute-scholarship-for-global-professionals",
        "https://si.se",
    ],
    33: [
        "https://www.campuschina.org",
        "https://www.campuschina.org/scholarships",
        "https://www.campuschina.org/universities",
        "https://www.chinesescholarshipcouncil.com",
    ],
    34: [
        "https://www.studyintaiwan.org",
        "https://www.studyintaiwan.org/taiwan_scholarship",
        "https://www.edutwscholarship.moe.gov.tw",
        "https://www.edutwscholarship.moe.gov.tw/scholarship/index",
    ],
    35: [
        "https://www.a-star.edu.sg/Scholarships/SINGA",
        "https://singa.a-star.edu.sg",
        "https://www.a-star.edu.sg",
        "https://singa.comp.nus.edu.sg",
    ],
    36: [
        "https://www.esteri.it/en/opportunita/borse-di-studio",
        "https://www.esteri.it/en/opportunita/borse-di-studio/per-cittadini-stranieri",
        "https://www.esteri.it",
        "https://studyinitaly.esteri.it",
    ],
    29: [
        "https://cscuk.fcdo.gov.uk/scholarships-developing-commonwealth-countries/",
        "https://cscuk.fcdo.gov.uk",
        "https://www.gov.uk/government/organisations/commonwealth-scholarship-commission",
    ],
}

# Heuristics to filter out non-content images
EXCLUDE_KEYWORDS = (
    "logo", "favicon", "icon", "sprite", "avatar", "spacer", "pixel", "blank",
    "placeholder", "ui", "button", "arrow", "chevron", "menu", "nav",
    "facebook", "twitter", "instagram", "youtube", "linkedin", "social",
    "cookie", "header-bg", "footer", "banner-bg", "ad-", "advert", "share",
    "loading", "spinner",
)
EXCLUDE_EXTS = (".svg", ".ico", ".gif")


def is_excluded_url(url: str) -> bool:
    if not url:
        return True
    lower = url.lower()
    if lower.endswith(EXCLUDE_EXTS):
        return True
    # data URIs
    if lower.startswith("data:"):
        return True
    for kw in EXCLUDE_KEYWORDS:
        if kw in lower:
            return True
    return False


def extract_from_soup(html: str, page_url: str) -> list[dict]:
    """Extract og:image, twitter:image, json-ld, and content <img> tags."""
    soup = BeautifulSoup(html, "html.parser")
    found: list[dict] = []

    # 1) og:image
    for tag in soup.find_all("meta", attrs={"property": "og:image"}):
        c = (tag.get("content") or "").strip()
        if c:
            found.append({
                "url": urljoin(page_url, c),
                "method": "og:image",
                "alt": (tag.get("alt") or "").strip() or None,
                "width": tag.get("width"),
                "height": tag.get("height"),
            })
    # 2) twitter:image
    for tag in soup.find_all("meta", attrs={"name": "twitter:image"}):
        c = (tag.get("content") or "").strip()
        if c:
            found.append({
                "url": urljoin(page_url, c),
                "method": "twitter:image",
                "alt": None,
                "width": None,
                "height": None,
            })
    # 3) JSON-LD
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        def walk(node):
            if isinstance(node, dict):
                if "image" in node:
                    img = node["image"]
                    if isinstance(img, str):
                        found.append({"url": urljoin(page_url, img), "method": "json-ld:image", "alt": None, "width": None, "height": None})
                    elif isinstance(img, list):
                        for i2 in img:
                            if isinstance(i2, str):
                                found.append({"url": urljoin(page_url, i2), "method": "json-ld:image", "alt": None, "width": None, "height": None})
                            elif isinstance(i2, dict) and i2.get("url"):
                                found.append({"url": urljoin(page_url, i2["url"]), "method": "json-ld:image", "alt": i2.get("name"), "width": i2.get("width"), "height": i2.get("height")})
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(data)
    # 4) content <img> tags in main/article
    content_selectors = ["article img", "main img", "[role='main'] img", ".content img", "section img", "body img"]
    seen_local = set()
    img_tags = []
    for sel in content_selectors:
        for tag in soup.select(sel):
            if id(tag) in seen_local:
                continue
            seen_local.add(id(tag))
            img_tags.append(tag)
    # If no content-scoped images, fall back to all imgs
    if not img_tags:
        img_tags = soup.find_all("img")
    for tag in img_tags:
        src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src") or ""
        if not src:
            continue
        src = src.strip()
        # skip srcset single
        full = urljoin(page_url, src)
        if is_excluded_url(full):
            continue
        w = tag.get("width")
        h = tag.get("height")
        try:
            w = int(w) if w and str(w).isdigit() else None
            h = int(h) if h and str(h).isdigit() else None
        except Exception:
            w, h = None, None
        found.append({
            "url": full,
            "method": "img_tag",
            "alt": (tag.get("alt") or "").strip() or None,
            "width": w,
            "height": h,
        })
    # Dedup by url keeping first method (og/twitter preferred since they come first)
    dedup = []
    seen_urls = set()
    for item in found:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        dedup.append(item)
    return dedup


def fetch(url: str, timeout: float = 30.0, ua: str = BROWSER_UA) -> httpx.Response | None:
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            return r
    except Exception as e:
        print(f"  ! fetch error: {e}")
        return None


def probe_image(url: str, timeout: float = 15.0) -> dict:
    headers = {"User-Agent": BROWSER_UA, "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            ct = r.headers.get("content-type", "")
            cl = r.headers.get("content-length")
            ok = r.status_code == 200 and ct.startswith("image/")
            # try to get dimensions
            w, h = None, None
            if ok and ct in ("image/png", "image/jpeg", "image/webp", "image/gif"):
                try:
                    from io import BytesIO
                    # light parser: PNG IHDR
                    data = r.content
                    if ct == "image/png" and len(data) > 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
                        w = int.from_bytes(data[16:20], "big")
                        h = int.from_bytes(data[20:24], "big")
                    elif ct in ("image/jpeg",) and len(data) > 4 and data[:2] == b"\xff\xd8":
                        # crude JPEG scan
                        i = 2
                        while i < len(data) - 9:
                            if data[i] != 0xff:
                                i += 1
                                continue
                            marker = data[i+1]
                            if marker in (0xc0, 0xc1, 0xc2, 0xc3):
                                h = int.from_bytes(data[i+5:i+7], "big")
                                w = int.from_bytes(data[i+7:i+9], "big")
                                break
                            seg_len = int.from_bytes(data[i+2:i+4], "big")
                            i += 2 + seg_len
                    elif ct == "image/gif" and len(data) > 10 and data[:6] in (b"GIF87a", b"GIF89a"):
                        w = int.from_bytes(data[6:8], "little")
                        h = int.from_bytes(data[8:10], "little")
                    elif ct == "image/webp" and len(data) > 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                        # VP8X chunk may include w/h
                        if data[12:16] == b"VP8X":
                            w = int.from_bytes(data[24:27], "little") + 1
                            h = int.from_bytes(data[27:30], "little") + 1
                        elif data[12:16] == b"VP8 " and len(data) > 29:
                            w = int.from_bytes(data[26:28], "little")
                            h = int.from_bytes(data[28:30], "little")
                except Exception:
                    pass
            return {"reachable": ok, "http_status": r.status_code, "content_type": ct, "content_length": int(cl) if cl and cl.isdigit() else None, "width": w, "height": h}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


def score_candidate(c: dict, scholarship_title: str) -> float:
    """Higher is better."""
    s = 0.0
    method = c.get("method", "")
    if method == "og:image":
        s += 5
    elif method == "twitter:image":
        s += 4
    elif method == "json-ld:image":
        s += 4
    elif method == "img_tag":
        s += 2
    w, h = c.get("width"), c.get("height")
    if w and h:
        if w >= 600 and h >= 300:
            s += 2
        elif w >= 400 and h >= 200:
            s += 1
        if w and h:
            ratio = w / h
            if 1.3 <= ratio <= 2.4:  # hero-ish
                s += 1.5
            elif 0.9 <= ratio <= 1.4:
                s += 0.5
    title = (scholarship_title or "").lower()
    alt = (c.get("alt") or "").lower()
    url = c.get("url", "").lower()
    # title tokens
    tokens = [t for t in re.split(r"[^a-z0-9]+", title) if len(t) > 3][:6]
    for t in tokens:
        if t in alt or t in url:
            s += 0.4
    # negative indicators
    if any(k in url for k in ["logo", "icon", "favicon", "avatar"]):
        s -= 10
    return s


def process_one(sch_id: int, urls: list[str], title: str) -> dict:
    out: dict = {
        "scholarship_id": sch_id,
        "title": title,
        "official_source_url": None,
        "best_image_url": None,
        "source_page": None,
        "discovery_method": None,
        "alt_text": None,
        "width": None,
        "height": None,
        "notes": "",
        "attempts": [],
        "all_candidates": [],
    }
    all_cands: list[dict] = []
    tried: list[dict] = []
    for url in urls:
        print(f"  -> {url}")
        r = fetch(url)
        if not r or r.status_code >= 400 or not r.text:
            tried.append({"url": url, "status": getattr(r, "status_code", None), "ok": False})
            time.sleep(0.5)
            continue
        ctype = r.headers.get("content-type", "")
        if "text/html" not in ctype and "xml" not in ctype:
            tried.append({"url": url, "status": r.status_code, "ok": False, "reason": f"non-html content-type {ctype}"})
            continue
        tried.append({"url": url, "status": r.status_code, "ok": True, "bytes": len(r.text)})
        cands = extract_from_soup(r.text, url)
        for c in cands:
            c["page_url"] = url
            c["sch_relevance_score"] = round(score_candidate(c, title), 3)
        all_cands.extend(cands)
        time.sleep(0.3)
    # Filter out excluded URLs from candidates
    filtered = [c for c in all_cands if not is_excluded_url(c["url"])]
    # Sort by relevance score
    filtered.sort(key=lambda c: c.get("sch_relevance_score", 0), reverse=True)
    out["all_candidates"] = filtered[:25]
    out["attempts"] = tried
    if filtered:
        best = filtered[0]
        out["best_image_url"] = best["url"]
        out["source_page"] = best.get("page_url")
        out["discovery_method"] = best["method"]
        out["alt_text"] = best.get("alt")
        out["width"] = best.get("width")
        out["height"] = best.get("height")
        out["official_source_url"] = urls[0]
        # Probe the image to get real dimensions and confirm reachability
        probe = probe_image(best["url"])
        out["image_probe"] = probe
        if probe.get("width") and probe.get("height"):
            out["width"] = probe["width"]
            out["height"] = probe["height"]
    else:
        out["notes"] = "No usable image candidates found on attempted pages."
    return out


def main():
    init_database()
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rows = s.execute(
            select(Scholarship.id, Scholarship.title, Scholarship.official_source_url).where(Scholarship.id.in_(TARGETS.keys()))
        ).all()
    finally:
        s.close()
    info = {r[0]: {"title": r[1], "official_source_url": r[2]} for r in rows}

    results = []
    for sid, urls in TARGETS.items():
        title = info.get(sid, {}).get("title", "")
        print(f"\n=== ID {sid}: {title} ===")
        res = process_one(sid, urls, title)
        if info.get(sid, {}).get("official_source_url"):
            res["db_official_source_url"] = info[sid]["official_source_url"]
        results.append(res)
        print(f"   best_image_url: {res.get('best_image_url')}")
    OUT.write_text(json.dumps(results, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved results to {OUT}")


if __name__ == "__main__":
    main()
