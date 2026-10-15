"""Fetch specific OFFICIAL pages for high-demand scholarships missing from the DB."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live_upcoming")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 25

# label -> (country, official page url)
TARGETS = {
    "HKPFS": ("Hong Kong", "https://cerg1.ugc.edu.hk/hkpfs/index.html"),
    "HKUSTpg": ("Hong Kong", "https://pg.hkust.edu.hk/prospective-students/scholarships-and-financial-aid"),
    "CUHKpg": ("Hong Kong", "https://www.gs.cuhk.edu.hk/admissions/scholarships-financial-aid"),
    "LaCaixa": ("Spain", "https://fundacionlacaixa.org/en/inphinit-young-researchers-fellowships-call"),
    "FundCarolina": ("Spain", "https://www.fundacioncarolina.es/"),
    "UC3M": ("Spain", "https://www.uc3m.es/master/scholarships-grants"),
    "UPC": ("Spain", "https://www.upc.edu/en/masters/scholarships-and-financial-aid"),
    "KAS": ("Germany", "https://kas.de/en/web/begabtenfoerderung-und-kultur/studienfoerderung"),
    "FriedNaumann": ("Germany", "https://www.freiheit.org/de/studienfoerderung"),
    "RosaLuxemburg": ("Germany", "https://www.rosalux.de/en/stiftung/studienwerk"),
    "Marshall": ("United Kingdom", "https://www.marshallscholarship.org/"),
    "Mitchell": ("Ireland", "https://www.us-irelandalliance.org/mitchell_scholarship"),
    "Churchill": ("United Kingdom", "https://www.churchillscholarship.org/"),
    "Saltire": ("United Kingdom", "https://www.scotland.org/study/saltire-scholarships"),
    "OxfordKobe": ("United Kingdom", "https://www.kobescholarship.ox.ac.uk/"),
    "Stanford": ("United States", "https://financialaid.stanford.edu/undergrad/how/"),
    "Columbia": ("United States", "https://undergrad.admissions.columbia.edu/apply/international"),
    "Vanderbilt": ("United States", "https://www.vanderbilt.edu/financialaid/scholarships/"),
    "Emory": ("United States", "https://apply.emory.edu/apply/scholarships-financial-aid/"),
    "USC": ("United States", "https://admission.usc.edu/apply/scholarships/"),
    "BU": ("United States", "https://www.bu.edu/finaid/types-of-aid/scholarships/"),
    "GWU": ("United States", "https://international.gwu.edu/"),
    "Banting": ("Canada", "https://banting.fellowships-bourses.gc.ca/en/home-accueil.html"),
    "UTSC": ("Canada", "https://www.utsc.utoronto.ca/admissions/international-scholarships"),
    "McGill": ("Canada", "https://www.mcgill.ca/entrance-scholarships/"),
    "KyotoIUP": ("Japan", "https://www.iup.kyoto-u.ac.jp/"),
    "U-TokyoPEAK": ("Japan", "https://peak.c.u-tokyo.ac.jp/"),
    "Waseda": ("Japan", "https://www.waseda.jp/inst/admission/other/scholarships/index.html"),
    "TohokuFGL": ("Japan", "https://www.eng.tohoku.ac.jp/admissions/fgl/"),
    "KUL": ("Belgium", "https://www.kuleuven.be/english/application/scholarships"),
    "VLIRUOS": ("Belgium", "https://www.vliruos.be/"),
    "NorwayQuota": ("Norway", "https://www.diku.no/en/"),
    "UIO": ("Norway", "https://www.uio.no/english/studies/admission/scholarships/"),
    "SJTU": ("China", "https://isc.sjtu.edu.cn/EN/"),
    "Polito": ("Italy", "https://www.polito.it/en/education/enrolment-and-fees/scholarships-and-subsidies"),
    "Pisa": ("Italy", "https://www.unipi.it/index.php/study/international-students/itemlist/category/borse-di-studio"),
    "ParisSaclay": ("France", "https://www.universite-paris-saclay.fr/en/admission/scholarships-and-financial-aid"),
    "UNIST": ("South Korea", "https://admission.unist.ac.kr/"),
    "Samsung": ("South Korea", "https://www.samsungfoundation.org/"),
    "Debrecen": ("Hungary", "https://unideb.hu/en/study-with-us/scholarships"),
    "Salamanca": ("Spain", "https://www.usal.es/"),
    "TUwien": ("Austria", "https://www.tuwien.at/en/studies/scholarships"),
    "NTNU": ("Norway", "https://www.ntnu.edu/studies/phd"),
    "Lund": ("Sweden", "https://www.lunduniversity.lu.se/admissions/tuition-fees-scholarships-and-funding"),
    "Chalmers": ("Sweden", "https://www.chalmers.se/en/education/scholarships/"),
    "ETH": ("Switzerland", "https://ethz.ch/en/studies/financial/scholarships.html"),
    "UZH": ("Switzerland", "https://www.uzh.ch/en/studies/application/scholarships.html"),
    "Imperial": ("United Kingdom", "https://www.imperial.ac.uk/study/fees-and-funding/scholarships/"),
    "UCL": ("United Kingdom", "https://www.ucl.ac.uk/scholarships/"),
    "Manchester": ("United Kingdom", "https://www.manchester.ac.uk/study/masters/funding/"),
    "Warwick": ("United Kingdom", "https://warwick.ac.uk/study/international/admissions/finance/scholarships/"),
    "Edinburgh": ("United Kingdom", "https://www.ed.ac.uk/studying/international/finance/scholarships"),
    "Bristol": ("United Kingdom", "https://www.bristol.ac.uk/students/support/finances/scholarships/"),
    "KCL": ("United Kingdom", "https://www.kcl.ac.uk/study/funding-and-scholarships"),
    "Sydney": ("Australia", "https://www.sydney.edu.au/study/applying/admission-pathways/scholarships.html"),
    "Monash": ("Australia", "https://www.monash.edu/study/fees-scholarships/scholarships"),
    "ANU": ("Australia", "https://www.anu.edu.au/study/scholarships"),
    "Melbourne": ("Australia", "https://scholarships.unimelb.edu.au/"),
    "TUd": ("Netherlands", "https://www.tudelft.nl/en/education/practical-matters/scholarships"),
    "RUG": ("Netherlands", "https://www.rug.nl/education/scholarships/"),
    "WUR": ("Netherlands", "https://www.wur.nl/en/education-programmes/prospective-students/scholarships.htm"),
    "NTUsg": ("Singapore", "https://www.ntu.edu.sg/admissions/graduate/financialmatters/scholarships"),
    "NUSsg": ("Singapore", "https://www.nus.edu.sg/oam/scholarships"),
    "SMU": ("Singapore", "https://www.smu.edu.sg/admissions/scholarships"),
    "TUM": ("Germany", "https://www.tum.de/en/studies/financing/scholarships"),
    "RWTH": ("Germany", "https://www.rwth-aachen.de/cms/root/studium/Studium-orientiert-an-Internationale/~fdn/Stipendien/"),
    "TUBS": ("Germany", "https://www.tu-braunschweig.de/en/studying/study-scholarships"),
    "Leibniz": ("Germany", "https://www.leibniz-gemeinschaft.de/en/careers/leibniz-postdoc-network/"),
}


def registrable_domain(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


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
                entry["text"] = clean_text(soup)[:14000]
            else:
                entry["error"] = f"status {r.status_code} ({r.headers.get('Content-Type','')[:40]})"
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        results[label] = entry
        t = entry.get("title") or ""
        print(f"{label:16s} {entry['status']} {entry.get('error') or t[:70]}")
    out = OUT_DIR / "top_country_evidence.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOutput: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
