"""Discover OFFICIAL logo image URLs for scholarships missing image_url (v2).

Fixes over v1: many official sites block HEAD requests (403) but serve the same
asset fine over GET with a browser User-Agent, so verification uses GET.
Unverified candidates are kept in the output for inspection; only ones that
return an image/* content type get ``verified: true``.

Read-only with respect to the database.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DB_PATH = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db")
OUT_DIR = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live_upcoming")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "logo_candidates_v2.json"

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
FETCH_TIMEOUT = 20
MIN_BYTES = 1024

SOURCE_COLUMNS = ["official_source_url", "application_link", "catalogue_url", "official_updates_url", "image_source_url"]

LOGO_HINT = re.compile(r"logo|brand|emblem|seal", re.I)


def registrable_domain(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def same_domain(a: str, b: str) -> bool:
    da, db = registrable_domain(a), registrable_domain(b)
    if not da or not db:
        return False
    return da == db or da.endswith("." + db) or db.endswith("." + da)


def fetch_page(url: str):
    try:
        r = requests.get(url, headers=UA, timeout=FETCH_TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            return r
    except Exception:
        return None
    return None


def verify_image(url: str) -> bool:
    try:
        g = requests.get(url, headers=UA, timeout=20, stream=True, allow_redirects=True)
        ctype = g.headers.get("Content-Type", "")
        ok = g.status_code == 200 and ctype.startswith("image/")
        g.close()
        return ok
    except Exception:
        return False


def extract_candidates(html: str, base_url: str, page_domain: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    seen = set()

    def add(cand_url, kind, alt, score):
        if not cand_url or cand_url.startswith("data:") or cand_url.startswith("javascript:"):
            return
        abs_url = urljoin(base_url, cand_url)
        if not abs_url.startswith("http"):
            return
        # page_domain is an already-extracted registrable domain, not a URL.
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
        if not href or "mask" in rel:
            continue
        if "icon" in rel:
            add(href, "link_icon", link.get("aria-label"), 60 if "apple-touch" in rel else 70)

    for meta in soup.find_all("meta", property=lambda v: v and v.lower() == "og:image"):
        add(meta.get("content"), "og_image", None, 50)

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        alt = img.get("alt") or ""
        cls = " ".join(img.get("class", []))
        ident = img.get("id") or ""
        hay = f"{src} {alt} {cls} {ident}".lower()
        score = 0
        if LOGO_HINT.search(hay):
            score = 90
        elif "logo" in src.lower():
            score = 85
        else:
            p, in_header = img, False
            for _ in range(6):
                p = p.parent if p else None
                if p is None:
                    break
                if (p.name or "").lower() in ("header", "nav"):
                    in_header = True
                    break
            if in_header:
                score = 40
        if score > 0:
            add(src, "img_logo" if score >= 80 else "img", alt or None, score)

    out.sort(key=lambda c: -c["score"])
    return out


def process_row(row: dict) -> dict:
    rid = row["id"]
    result = {"id": rid, "title": row["title"], "country": row["country"], "candidates": [], "verified": [], "notes": []}
    urls = [u for u in (row.get(c) for c in SOURCE_COLUMNS) if u and u.startswith("http")]
    if not urls:
        result["notes"].append("no source urls")
        return result

    tried, candidates = 0, []
    for u in urls:
        if tried >= 3:
            break
        resp = fetch_page(u)
        tried += 1
        if not resp:
            continue
        page_dom = registrable_domain(resp.url)
        for c in extract_candidates(resp.text, resp.url, page_dom):
            c["from_page"] = resp.url
            candidates.append(c)

    dedup = {}
    for c in candidates:
        if c["url"] not in dedup or c["score"] > dedup[c["url"]]["score"]:
            dedup[c["url"]] = c
    ranked = sorted(dedup.values(), key=lambda c: -c["score"])[:8]
    result["candidates"] = ranked

    verified = []
    for c in ranked[:6]:
        if verify_image(c["url"]):
            c["verified"] = True
            verified.append(c)
            if len(verified) >= 3:
                break
    result["verified"] = verified
    if not verified:
        result["notes"].append("no verified logo candidates")
    return result


def main() -> int:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cols = ", ".join(SOURCE_COLUMNS)
    rows = cur.execute(
        f"SELECT id, title, country, {cols} FROM scholarships "
        "WHERE is_archived=0 AND (image_url IS NULL OR image_url='') ORDER BY id"
    ).fetchall()
    con.close()
    todo = [dict(r) for r in rows]
    print(f"Rows needing logos: {len(todo)}")

    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(process_row, r): r for r in todo}
        done = 0
        for fut in as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as e:
                r = futs[fut]
                results.append({"id": r["id"], "title": r["title"], "country": r["country"], "candidates": [], "verified": [], "notes": [f"error: {e}"]})
            done += 1
            if done % 25 == 0:
                print(f"  processed {done}/{len(todo)}")
                OUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    results.sort(key=lambda r: r["id"])
    OUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    with_cand = sum(1 for r in results if r.get("verified"))
    print(f"\nDone. Rows with VERIFIED logo candidates: {with_cand}/{len(results)}")
    print(f"Output: {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
