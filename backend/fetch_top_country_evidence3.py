"""Third round: specific sub-pages for the highest-value new records."""

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
TIMEOUT = 30

TARGETS = {
    "CUHK_VC": ("Hong Kong", "https://www.gs.cuhk.edu.hk/admissions/scholarships-financial-aid/vice-chancellor-phd-scholarship-scheme"),
    "CUHK_HKFS": ("Hong Kong", "https://www.gs.cuhk.edu.hk/admissions/scholarships-financial-aid/hong-kong-phd-fellowship-scheme"),
    "VLIR_study": ("Belgium", "https://www.vliruos.be/get-funded/study-scholarships"),
    "KyotoUP_adm": ("Japan", "https://www.iup.kyoto-u.ac.jp/admissions"),
    "Churchill_apply": ("United Kingdom", "https://www.churchillscholarship.org/apply/"),
    "Bham_search": ("United Kingdom", "https://www.birmingham.ac.uk/study/international/fees/scholarships/chancellors"),
    "USC_merit": ("United States", "https://admission.usc.edu/cost-and-financial-aid/scholarships/"),
    "Stanford_aid": ("United States", "https://financialaid.stanford.edu/undergrad/how/aid-enhances/"),
    "McGill_major": ("Canada", "https://www.mcgill.ca/studentaid/scholarships-aid/future-undergrads/entrance-scholarships/major"),
    "Waterloo_int": ("Canada", "https://uwaterloo.ca/future-students/scholarships/international"),
    "ETH_ESOP": ("Switzerland", "https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship.html"),
    "Melb_MRS": ("Australia", "https://scholarships.unimelb.edu.au/awards/graduate-research-scholarships"),
    "UNIL_master": ("Switzerland", "https://www.unil.ch/formations/en/home/menuinst/mobilite/bourses.html"),
    "EPFL_exc": ("Switzerland", "https://www.epfl.ch/education/master/master-excellence-fellowships/"),
    "ETH_esop_de": ("Switzerland", "https://ethz.ch/en/studies/financial/scholarships.html"),
}


def clean_text(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))


def main() -> int:
    results = {}
    for label, (country, url) in TARGETS.items():
        entry = {"country": country, "url": url, "status": None, "final_url": None, "title": None, "text": None, "error": None}
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
            entry["status"] = r.status_code
            entry["final_url"] = r.url
            if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
                soup = BeautifulSoup(r.text, "html.parser")
                entry["title"] = (soup.title.string.strip() if soup.title and soup.title.string else None)
                entry["text"] = clean_text(soup)[:18000]
            else:
                entry["error"] = f"status {r.status_code} ({r.headers.get('Content-Type','')[:40]})"
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        results[label] = entry
        t = entry.get("title") or ""
        print(f"{label:14s} {entry['status']} {entry.get('error') or t[:60]}")
    out = OUT_DIR / "top_country_evidence3.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOutput: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
