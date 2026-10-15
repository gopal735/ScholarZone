"""Final targeted fetch for remaining high-value records."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live_upcoming")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TARGETS = {
    "Marshall_main": ("United Kingdom", "https://www.marshallscholarship.org/apply"),
    "Yenching_en": ("China", "https://yenching.pku.edu.cn/en/"),
    "Schwarzman_prog": ("China", "https://www.schwarzmanscholars.org/program/"),
    "CUHK_VC2": ("Hong Kong", "https://www.gs.cuhk.edu.hk/admissions/scholarships-financial-aid"),
    "CUHK_HKPFS": ("Hong Kong", "https://www.gs.cuhk.edu.hk/admissions/scholarships-financial-aid/hong-kong-phd-fellowship-scheme"),
    "Churchill_prog": ("United Kingdom", "https://www.churchillscholarship.org/about/"),
    "Rhodes_value": ("United Kingdom", "https://www.rhodeshouse.ox.ac.uk/scholarships/the-rhodes-scholarship/what-does-the-rhodes-scholarship-cover/"),
    "Stanford_int": ("United States", "https://financialaid.stanford.edu/undergrad/how/"),
    "Columbia_aid": ("United States", "https://undergrad.admissions.columbia.edu/apply/applying-aid"),
    "USC_merit2": ("United States", "https://admission.usc.edu/cost-and-financial-aid/scholarships/"),
    "McGill_ent": ("Canada", "https://www.mcgill.ca/studentaid/scholarships-aid/future-undergrads/entrance-scholarships"),
    "KyotoUP": ("Japan", "https://www.iup.kyoto-u.ac.jp/"),
    "VLIR": ("Belgium", "https://www.vliruos.be/get-funded/study-scholarships"),
    "Bham": ("United Kingdom", "https://www.birmingham.ac.uk/study/international/fees/scholarships"),
    "Imperial_search": ("United Kingdom", "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"),
}


def clean_text(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))


def main() -> int:
    results = {}
    for label, (country, url) in TARGETS.items():
        entry = {"country": country, "url": url, "status": None, "final_url": None, "title": None, "text": None, "error": None}
        for attempt in range(3):
            try:
                r = requests.get(url, headers=UA, timeout=40, allow_redirects=True)
                entry["status"] = r.status_code
                entry["final_url"] = r.url
                if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
                    soup = BeautifulSoup(r.text, "html.parser")
                    entry["title"] = (soup.title.string.strip() if soup.title and soup.title.string else None)
                    entry["text"] = clean_text(soup)[:20000]
                    entry["error"] = None
                    break
                entry["error"] = f"status {r.status_code}"
            except Exception as e:
                entry["error"] = f"{type(e).__name__}: {str(e)[:100]}"
        results[label] = entry
        t = entry.get("title") or ""
        print(f"{label:18s} {entry['status']} {entry.get('error') or t[:55]}")
    out = OUT_DIR / "top_country_evidence5.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOutput: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
