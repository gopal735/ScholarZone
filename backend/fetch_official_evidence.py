"""Fetch official scholarship pages for gap countries and extract evidence.

Web search is unavailable (provider allowance exhausted), so this fetches a
curated list of OFFICIAL awarding-body URLs directly. For each page it stores
the extracted text and same-domain logo candidates so records can be built
from what the awarding body actually publishes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live_upcoming")
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 25

PAGES: dict[str, list[str]] = {
    "Ukraine": [
        "https://studyinukraine.gov.ua/fees-and-scholarships/",
    ],
    "Greece": [
        "https://www.iky.gr/en/scholarships/",
        "https://www.iky.gr/ypotrofies/",
    ],
    "Romania": [
        "https://mae.ro/en/node/48356",
        "https://www.edu.ro/index.php/articles/burse",
    ],
    "Bulgaria": [
        "https://www.mon.bg/bg/100369",
        "https://www.mon.bg/bg/100365",
    ],
    "Croatia": [
        "http://www.ceepus.info/",
        "https://www.carnet.hr/en/ceepus",
    ],
    "Slovenia": [
        "https://scholarships.cmepius.si/",
        "https://www.gov.si/en/news/2022-02-08-call-for-applications-for-slovene-scholarships-for-foreign-students/",
    ],
    "Iceland": [
        "https://english.hi.is/scholarships",
        "https://www.ru.is/en/scholarships",
    ],
    "Malta": [
        "https://scholarships.gov.mt/",
        "https://www.gov.mt/en/Government/Pages/Government%20of%20Malta%20Scholarships.aspx",
    ],
    "Cyprus": [
        "https://www.moec.gov.cy/dme/en/",
    ],
    "Georgia": [
        "https://study.mes.gov.ge/",
        "https://mes.gov.ge/",
    ],
    "Armenia": [
        "https://www.edu.am/en/",
    ],
    "Lithuania": [
        "https://www.lmt.lt/en/",
        "https://studyin.lt/scholarships/",
    ],
    "Nepal": [
        "https://moest.gov.np/",
        "https://tribhuvan-university.edu.np/",
    ],
    "Mongolia": [
        "https://mohe.gov.mn/",
    ],
    "Cambodia": [
        "https://www.moeys.gov.kh/index.php/en/",
    ],
    "Macau": [
        "https://www.fmac.org.mo/en/",
        "https://www.dsedj.gov.mo/",
    ],
    "Maldives": [
        "https://www.mnu.edu.mv/",
    ],
    "Botswana": [
        "https://www.biust.ac.bw/",
        "https://www.gov.bw/",
    ],
    "Namibia": [
        "https://www.namcol.edu.na/",
    ],
    "Kenya": [
        "https://www.education.go.ke/",
    ],
    "Tanzania": [
        "https://www.tamisemi.go.tz/",
    ],
    "Ethiopia": [
        "https://www.aau.edu.et/",
    ],
    "Uruguay": [
        "https://www.anii.org.uy/",
    ],
    "Paraguay": [
        "https://www.becal.gov.py/",
    ],
    "Bolivia": [
        "https://www.minedu.gob.bo/",
    ],
    "Cuba": [
        "https://www.embajadadecuba.org/",
    ],
    "Trinidad and Tobago": [
        "https://www.uwi.edu/",
    ],
    "Panama": [
        "https://www.ifarhu.gob.pa/",
    ],
    "Jamaica": [
        "https://www.moey.gov.jm/",
    ],
    "Bahamas": [
        "https://www.bahamas.gov.bs/",
    ],
}

LOGO_HINT = re.compile(r"logo|brand|emblem|seal", re.I)


def registrable_domain(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def same_domain(a: str, b: str) -> bool:
    da, db = registrable_domain(a), registrable_domain(b)
    if not da or not db:
        return False
    return da == db or da.endswith("." + db) or db.endswith("." + da)


def clean_text(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    return text


def extract_logos(soup: BeautifulSoup, base_url: str, page_domain: str) -> list[dict]:
    out, seen = [], set()

    def add(u, kind, alt, score):
        if not u or u.startswith("data:"):
            return
        abs_url = urljoin(base_url, u)
        if not abs_url.startswith("http") or not same_domain(abs_url, page_domain) or abs_url in seen:
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


def fetch(url: str) -> dict:
    entry = {"url": url, "status": None, "final_url": None, "title": None, "text": None, "logos": [], "error": None}
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        entry["status"] = r.status_code
        entry["final_url"] = r.url
        ctype = r.headers.get("Content-Type", "")
        if r.status_code == 200 and "text/html" in ctype:
            soup = BeautifulSoup(r.text, "html.parser")
            entry["title"] = (soup.title.string.strip() if soup.title and soup.title.string else None)
            entry["text"] = clean_text(soup)[:12000]
            entry["logos"] = extract_logos(soup, r.url, registrable_domain(r.url))[:8]
        else:
            entry["error"] = f"non-html or status {r.status_code} ({ctype[:40]})"
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return entry


def main() -> int:
    results = {}
    for country, urls in PAGES.items():
        results[country] = []
        for u in urls:
            print(f"fetching {country}: {u}")
            results[country].append(fetch(u))
    out = OUT_DIR / "official_page_evidence.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for c in results.values() for e in c if e["status"] == 200)
    print(f"\nFetched {ok} pages successfully. Output: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
