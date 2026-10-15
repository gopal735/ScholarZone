"""Second round: corrected official URLs for high-demand scholarships missing from the DB."""

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
    "KAS2": ("Germany", "https://www.kas.de/de/web/begabtenfoerderung-und-kultur/studienfoerderung"),
    "FriedNaumann2": ("Germany", "https://www.freiheit.org/en/topics/studienfoerderung"),
    "Marshall2": ("United Kingdom", "https://www.marshallscholarship.org/apply"),
    "Mitchell2": ("Ireland", "https://www.us-irelandalliance.org/mitchell_scholarship/apply"),
    "LaCaixa2": ("Spain", "https://fundacionlacaixa.org/en/inphinit-doctoral-fellowships"),
    "Carolina2": ("Spain", "https://www.fundacioncarolina.es/formacion/becas-de-postgrado/"),
    "Melbourne2": ("Australia", "https://scholarships.unimelb.edu.au/content/scholarships/graduate-research-scholarships"),
    "ETH2": ("Switzerland", "https://ethz.ch/en/studies/financial/scholarships/excellencescholarship.html"),
    "UZH2": ("Switzerland", "https://www.uzh.ch/cmsssl/en/studies/application/scholarships.html"),
    "Waseda2": ("Japan", "https://www.waseda.jp/inst/admission/international/en/"),
    "Tohoku2": ("Japan", "https://www.eng.tohoku.ac.jp/english/"),
    "Polito2": ("Italy", "https://www.polito.it/en/education/enrolment-and-fees/scholarships"),
    "UC3M2": ("Spain", "https://www.uc3m.es/postgraduate/scholarships-and-grants"),
    "CUHK2": ("Hong Kong", "https://www.gs.cuhk.edu.hk/"),
    "HKUST2": ("Hong Kong", "https://pg.hkust.edu.hk/prospective-students/financial-support"),
    "Imperial2": ("United Kingdom", "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/?study_level=postgraduate-taught"),
    "Lund2": ("Sweden", "https://www.lunduniversity.lu.se/admissions/tuition-fees-scholarships-and-funding/scholarships"),
    "Chalmers2": ("Sweden", "https://www.chalmers.se/en/education/scholarships/avancez-scholarships/"),
    "WUR2": ("Netherlands", "https://www.wur.nl/en/education-programmes/prospective-student/scholarships.htm"),
    "ParisSaclay2": ("France", "https://www.universite-paris-saclay.fr/en/admission/scholarships-and-financial-aid"),
    "KyotoU2": ("Japan", "https://www.iup.kyoto-u.ac.jp/admissions/"),
    "DeMontfort": ("United Kingdom", "https://www.dmu.ac.uk/international/scholarships/"),
    "Sheffield": ("United Kingdom", "https://www.sheffield.ac.uk/international/students/fees-and-scholarships"),
    "Glasgow": ("United Kingdom", "https://www.gla.ac.uk/scholarships/"),
    "Birmingham": ("United Kingdom", "https://www.birmingham.ac.uk/International/students/finance/scholarships/index.aspx"),
    "Nottingham": ("United Kingdom", "https://www.nottingham.ac.uk/studywithus/international-applicants/scholarships.aspx"),
    "Leeds": ("United Kingdom", "https://www.leeds.ac.uk/info/130531/international_students/69/scholarships"),
    "Cardiff": ("United Kingdom", "https://www.cardiff.ac.uk/study/international/funding-and-scholarships"),
    "StAndrews": ("United Kingdom", "https://www.st-andrews.ac.uk/study/fees-and-funding/scholarships/"),
    "Adelaide": ("Australia", "https://www.adelaide.edu.au/scholarships/"),
    "UWA": ("Australia", "https://www.uwa.edu.au/study/scholarships"),
    "Swinburne": ("Australia", "https://www.swinburne.edu.au/study/scholarships/"),
    "Toronto": ("Canada", "https://future.utoronto.ca/finances/scholarships/"),
    "Waterloo": ("Canada", "https://uwaterloo.ca/future-students/scholarships"),
    "Alberta": ("Canada", "https://www.ualberta.ca/admissions-international/tuition-and-scholarships/index.html"),
    "SFU": ("Canada", "https://www.sfu.ca/students/financialaid/scholarships.html"),
    "UniMelb": ("Australia", "https://scholarships.unimelb.edu.au/"),
    "SKKU": ("South Korea", "https://www.skku.edu/eng/"),
    "Yonsei2": ("South Korea", "https://www.yonsei.ac.kr/en_sc/admission/scholarship.jsp"),
    "POSTECH": ("South Korea", "https://admission.postech.ac.kr/eng/"),
    "UST": ("South Korea", "https://www.ust.ac.kr/eng/"),
    "Tsinghua2": ("China", "https://www.tsinghua.edu.cn/en/Admissions/International_Students_Admission.htm"),
    "Fudan2": ("China", "https://iso.fudan.edu.cn/"),
    "ZJU2": ("China", "https://www.zju.edu.cn/english/"),
    "SJTU2": ("China", "https://en.sjtu.edu.cn/"),
    "CityU": ("Hong Kong", "https://www.cityu.edu.hk/sgs/"),
    "PolyU": ("Hong Kong", "https://www.polyu.edu.hk/en/study/pg/scholarships/"),
    "HKBU": ("Hong Kong", "https://www.hkbu.edu.hk/en/main/scholarships.html"),
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
                entry["text"] = clean_text(soup)[:16000]
            else:
                entry["error"] = f"status {r.status_code} ({r.headers.get('Content-Type','')[:40]})"
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        results[label] = entry
        t = entry.get("title") or ""
        print(f"{label:14s} {entry['status']} {entry.get('error') or t[:60]}")
    out = OUT_DIR / "top_country_evidence2.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOutput: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
