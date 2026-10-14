"""Retry the failed scholarships (28 Chevening, 34 Taiwan) with longer timeout, alt UA, and Google cache fallback."""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend')
from app.database import get_engine, init_database
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.models import Scholarship

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CHROME_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_targeted_retry.json')

CHEVENING_URLS = [
    "https://www.chevening.org/scholarships/",
    "https://www.chevening.org/scholarships/who-can-apply/",
    "https://www.chevening.org/about-chevening/",
    "https://www.chevening.org/apply/",
    "https://www.chevening.org",
    "https://webcache.googleusercontent.com/search?q=cache:www.chevening.org/scholarships/",
    "https://web.archive.org/web/2024/https://www.chevening.org/scholarships/",
]
TAIWAN_URLS = [
    "https://www.studyintaiwan.org",
    "https://www.studyintaiwan.org/taiwan_scholarship",
    "https://www.studyintaiwan.org/programs",
    "https://www.edutwscholarship.moe.gov.tw",
    "https://www.edutwscholarship.moe.gov.tw/scholarship/index",
    "https://web.archive.org/web/2024/https://www.studyintaiwan.org/taiwan_scholarship",
]

EXCLUDE_KEYWORDS = ("logo", "favicon", "icon", "sprite", "avatar", "spacer", "pixel", "blank", "placeholder", "ui", "button", "arrow", "chevron", "menu", "nav", "facebook", "twitter", "instagram", "youtube", "linkedin", "social", "cookie", "header-bg", "footer", "banner-bg", "ad-", "advert", "share", "loading", "spinner")
EXCLUDE_EXTS = (".svg", ".ico", ".gif")


def is_excluded_url(url: str) -> bool:
    if not url: return True
    lower = url.lower()
    if lower.endswith(EXCLUDE_EXTS): return True
    if lower.startswith("data:"): return True
    for kw in EXCLUDE_KEYWORDS:
        if kw in lower: return True
    return False


def extract(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for tag in soup.find_all("meta", attrs={"property": "og:image"}):
        c = (tag.get("content") or "").strip()
        if c: found.append({"url": urljoin(page_url, c), "method": "og:image", "alt": None, "width": tag.get("width"), "height": tag.get("height")})
    for tag in soup.find_all("meta", attrs={"name": "twitter:image"}):
        c = (tag.get("content") or "").strip()
        if c: found.append({"url": urljoin(page_url, c), "method": "twitter:image", "alt": None, "width": None, "height": None})
    for s in soup.find_all("script", type="application/ld+json"):
        try: data = json.loads(s.string or "{}")
        except Exception: continue
        def walk(n):
            if isinstance(n, dict):
                if "image" in n:
                    img = n["image"]
                    if isinstance(img, str): found.append({"url": urljoin(page_url, img), "method": "json-ld:image", "alt": None, "width": None, "height": None})
                    elif isinstance(img, list):
                        for i2 in img:
                            if isinstance(i2, str): found.append({"url": urljoin(page_url, i2), "method": "json-ld:image", "alt": None, "width": None, "height": None})
                            elif isinstance(i2, dict) and i2.get("url"): found.append({"url": urljoin(page_url, i2["url"]), "method": "json-ld:image", "alt": i2.get("name"), "width": i2.get("width"), "height": i2.get("height")})
                for v in n.values(): walk(v)
            elif isinstance(n, list):
                for v in n: walk(v)
        walk(data)
    for sel in ["article img", "main img", "[role='main'] img", ".content img", "section img", "body img"]:
        for tag in soup.select(sel):
            src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src") or ""
            if not src: continue
            full = urljoin(page_url, src.strip())
            if is_excluded_url(full): continue
            w, h = tag.get("width"), tag.get("height")
            try:
                w = int(w) if w and str(w).isdigit() else None
                h = int(h) if h and str(h).isdigit() else None
            except: w, h = None, None
            found.append({"url": full, "method": "img_tag", "alt": (tag.get("alt") or "").strip() or None, "width": w, "height": h})
    dedup, seen = [], set()
    for f in found:
        if f["url"] in seen: continue
        seen.add(f["url"]); dedup.append(f)
    return dedup


def fetch(url, timeout, ua):
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            return client.get(url)
    except Exception as e:
        print(f"  ! {type(e).__name__}: {e}"); return None


def score(c, title):
    s = 0.0
    m = c.get("method", "")
    if m == "og:image": s += 5
    elif m == "twitter:image": s += 4
    elif m == "json-ld:image": s += 4
    elif m == "img_tag": s += 2
    w, h = c.get("width"), c.get("height")
    if w and h:
        if w >= 600 and h >= 300: s += 2
        elif w >= 400 and h >= 200: s += 1
        if 1.3 <= w/h <= 2.4: s += 1.5
        elif 0.9 <= w/h <= 1.4: s += 0.5
    title_l = (title or "").lower()
    alt = (c.get("alt") or "").lower()
    url = c.get("url", "").lower()
    for t in re.split(r"[^a-z0-9]+", title_l):
        if len(t) > 3 and (t in alt or t in url): s += 0.4
    if any(k in url for k in ["logo", "icon", "favicon", "avatar"]): s -= 10
    return s


def probe(url, timeout=15):
    headers = {"User-Agent": BROWSER_UA, "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            ct = r.headers.get("content-type", "")
            cl = r.headers.get("content-length")
            ok = r.status_code == 200 and ct.startswith("image/")
            w, h = None, None
            if ok and ct in ("image/png", "image/jpeg", "image/webp", "image/gif"):
                data = r.content
                try:
                    if ct == "image/png" and len(data) > 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
                        w = int.from_bytes(data[16:20], "big"); h = int.from_bytes(data[20:24], "big")
                    elif ct == "image/jpeg" and len(data) > 4 and data[:2] == b"\xff\xd8":
                        i = 2
                        while i < len(data) - 9:
                            if data[i] != 0xff: i += 1; continue
                            mk = data[i+1]
                            if mk in (0xc0,0xc1,0xc2,0xc3):
                                h = int.from_bytes(data[i+5:i+7], "big"); w = int.from_bytes(data[i+7:i+9], "big"); break
                            seg = int.from_bytes(data[i+2:i+4], "big"); i += 2 + seg
                    elif ct == "image/gif" and len(data) > 10 and data[:6] in (b"GIF87a", b"GIF89a"):
                        w = int.from_bytes(data[6:8], "little"); h = int.from_bytes(data[8:10], "little")
                    elif ct == "image/webp" and len(data) > 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                        if data[12:16] == b"VP8X":
                            w = int.from_bytes(data[24:27], "little") + 1; h = int.from_bytes(data[27:30], "little") + 1
                except: pass
            return {"reachable": ok, "http_status": r.status_code, "content_type": ct, "width": w, "height": h, "content_length": int(cl) if cl and cl.isdigit() else None}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


def process(sid, title, urls):
    print(f"\n=== ID {sid}: {title} ===")
    all_cands, tried = [], []
    for url in urls:
        print(f"  -> {url}")
        r = fetch(url, timeout=45, ua=CHROME_UA)
        if not r or r.status_code >= 400 or not r.text:
            tried.append({"url": url, "status": getattr(r, "status_code", None), "ok": False})
            # retry once with alt UA and longer timeout
            r2 = fetch(url, timeout=60, ua=BROWSER_UA)
            if r2 and r2.status_code < 400 and r2.text:
                r = r2
            else:
                time.sleep(0.5); continue
        ctype = r.headers.get("content-type", "")
        if "text/html" not in ctype and "xml" not in ctype:
            tried.append({"url": url, "status": r.status_code, "ok": False, "reason": ctype}); continue
        tried.append({"url": url, "status": r.status_code, "ok": True, "bytes": len(r.text)})
        cands = extract(r.text, url)
        for c in cands: c["page_url"] = url; c["sch_relevance_score"] = round(score(c, title), 3)
        all_cands.extend(cands)
        time.sleep(0.3)
    filtered = [c for c in all_cands if not is_excluded_url(c["url"])]
    filtered.sort(key=lambda c: c.get("sch_relevance_score", 0), reverse=True)
    res = {"scholarship_id": sid, "title": title, "best_image_url": None, "source_page": None, "discovery_method": None, "alt_text": None, "width": None, "height": None, "notes": "", "attempts": tried, "all_candidates": filtered[:25]}
    if filtered:
        b = filtered[0]
        res["best_image_url"] = b["url"]; res["source_page"] = b.get("page_url"); res["discovery_method"] = b["method"]; res["alt_text"] = b.get("alt"); res["width"] = b.get("width"); res["height"] = b.get("height")
        p = probe(b["url"]); res["image_probe"] = p
        if p.get("width") and p.get("height"): res["width"] = p["width"]; res["height"] = p["height"]
    else:
        res["notes"] = "No usable image candidates found on attempted pages."
    print(f"   best_image_url: {res.get('best_image_url')}")
    return res


def main():
    init_database()
    engine = get_engine()
    Session = sessionmaker(bind=engine); s = Session()
    try:
        rows = s.execute(select(Scholarship.id, Scholarship.title).where(Scholarship.id.in_([28, 34]))).all()
    finally: s.close()
    info = {r[0]: r[1] for r in rows}
    results = [process(28, info.get(28, "Chevening"), CHEVENING_URLS), process(34, info.get(34, "Taiwan"), TAIWAN_URLS)]
    OUT.write_text(json.dumps(results, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved retry results to {OUT}")


if __name__ == "__main__":
    main()
