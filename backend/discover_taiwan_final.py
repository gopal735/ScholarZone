"""Final attempt for Taiwan Scholarship (ID 34) using Wayback variants and known MOE info pages."""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

OUT = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_taiwan_final.json')
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

URLS = [
    "https://web.archive.org/web/2024/https://www.studyintaiwan.org/taiwan_scholarship",
    "https://web.archive.org/web/2023/https://www.studyintaiwan.org/taiwan_scholarship",
    "https://web.archive.org/web/2022/https://www.studyintaiwan.org/",
    "https://web.archive.org/web/2023/https://www.edutwscholarship.moe.gov.tw",
    "https://web.archive.org/web/2024/https://en.moe.gov.tw/",
    "https://web.archive.org/web/2023/https://english.moe.gov.tw/cp-1-37408-1.html",
    "https://web.archive.org/web/2024/https://english.moe.gov.tw/cp-1-37408-1.html",
]

EXCLUDE_KEYWORDS = ("logo", "favicon", "icon", "sprite", "avatar", "spacer", "pixel", "blank", "placeholder", "ui", "button", "arrow", "chevron", "menu", "nav", "facebook", "twitter", "instagram", "youtube", "linkedin", "social", "cookie", "header-bg", "footer", "banner-bg", "ad-", "advert", "share", "loading", "spinner")
EXCLUDE_EXTS = (".svg", ".ico", ".gif")


def is_excluded(url):
    if not url: return True
    u = url.lower()
    if u.endswith(EXCLUDE_EXTS) or u.startswith("data:"): return True
    for k in EXCLUDE_KEYWORDS:
        if k in u: return True
    return False


def extract(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for tag in soup.find_all("meta", attrs={"property": "og:image"}):
        c = (tag.get("content") or "").strip()
        if c: found.append({"url": urljoin(page_url, c), "method": "og:image", "alt": None})
    for tag in soup.find_all("meta", attrs={"name": "twitter:image"}):
        c = (tag.get("content") or "").strip()
        if c: found.append({"url": urljoin(page_url, c), "method": "twitter:image", "alt": None})
    for sel in ["article img", "main img", ".content img", "section img", "body img"]:
        for tag in soup.select(sel):
            src = tag.get("src") or tag.get("data-src") or ""
            if not src: continue
            full = urljoin(page_url, src.strip())
            if is_excluded(full): continue
            found.append({"url": full, "method": "img_tag", "alt": (tag.get("alt") or "").strip() or None})
    dedup, seen = [], set()
    for f in found:
        if f["url"] in seen: continue
        seen.add(f["url"]); dedup.append(f)
    return dedup


def fetch(url, timeout=60):
    headers = {"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            return client.get(url)
    except Exception as e:
        print(f"  ! {type(e).__name__}: {e}"); return None


all_cands, tried = [], []
for url in URLS:
    print(f"-> {url}")
    r = fetch(url)
    if not r or r.status_code >= 400 or not r.text:
        tried.append({"url": url, "status": getattr(r, "status_code", None), "ok": False}); continue
    tried.append({"url": url, "status": r.status_code, "ok": True, "bytes": len(r.text)})
    cands = extract(r.text, url)
    for c in cands: c["page_url"] = url
    all_cands.extend(cands)
    time.sleep(0.5)

filtered = [c for c in all_cands if not is_excluded(c["url"])]
print(f"\nTotal filtered candidates: {len(filtered)}")
for c in filtered[:30]:
    print(f"  - [{c['method']}] {c['url']}  alt={c.get('alt')}")

OUT.write_text(json.dumps({"attempts": tried, "candidates": filtered}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved to {OUT}")
