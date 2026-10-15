"""Final round: remaining high-value top-demand scholarships."""

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
    "Schwarzman": ("China", "https://www.schwarzmanscholars.org/"),
    "Yenching": ("China", "https://yenching.pku.edu.cn/"),
    "Rhodes": ("United Kingdom", "https://www.rhodeshouse.ox.ac.uk/scholarships/the-rhodes-scholarship/"),
    "Marshall": ("United Kingdom", "https://www.marshallscholarship.org/"),
    "Mitchell": ("Ireland", "https://www.us-irelandalliance.org/mitchell_scholarship"),
    "StGall": ("Switzerland", "https://unisg.ch/en/studium/master/bewerbung/scholarships/"),
    "StGallenB": ("Switzerland", "https://www.study-in-switzerland.plus/en/bachelor-scholarship/"),
    "KyotoU_eng": ("Japan", "https://www.kyoto-u.ac.jp/en/education-campus/education-and-admissions/admissions/international-students"),
    "KUIS": ("Japan", "https://www.iup.kyoto-u.ac.jp/scholarship/"),
    "EPFL_Dec": ("Switzerland", "https://www.epfl.ch/education/master/master-excellence-fellowships/application-deadlines/"),
    "BhamInt": ("United Kingdom", "https://www.birmingham.ac.uk/study/international/fees/scholarships"),
    "UNSW": ("Australia", "https://www.unsw.edu.au/study/scholarships"),
    "USyd": ("Australia", "https://www.sydney.edu.au/study/applying/admission-pathways/scholarships.html"),
    "Monash": ("Australia", "https://www.monash.edu/study/fees-scholarships/scholarships/find-a-scholarship"),
    "Melbourne": ("Australia", "https://scholarships.unimelb.edu.au/awards"),
    "Imperial_Pres": ("United Kingdom", "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"),
    "OxfordInt": ("United Kingdom", "https://www.ox.ac.uk/admissions/undergraduate/fees-and-funding/oxford-support"),
    "CambridgeInt": ("United Kingdom", "https://www.undergraduate.study.cam.ac.uk/fees-and-financial-support"),
    "NUSGrad": ("Singapore", "https://www.nus.edu.sg/oam/scholarships/freshmen-scholarships/singapore-citizens-or-pr"),
    "SMUsch": ("Singapore", "https://admissions.smu.edu.sg/scholarships"),
    "KAIST": ("South Korea", "https://admission.kaist.ac.kr/international/guideline/"),
    "POSTECH2": ("South Korea", "https://www.postech.ac.kr/eng/admissions/"),
    "HKUST": ("Hong Kong", "https://join.hkust.edu.hk/scholarships"),
    "PolyU2": ("Hong Kong", "https://www.polyu.edu.hk/en/study/pg/scholarships-and-financial-support/"),
    "CityU2": ("Hong Kong", "https://www.admo.cityu.edu.hk/scp/scholarship/"),
    "Tsinghua": ("China", "https://join.tsinghua.edu.cn/"),
    "Fudan_int": ("China", "https://iso.fudan.edu.cn/en/"),
    "Waseda_sch": ("Japan", "https://www.waseda.jp/inst/admission/other/scholarships/"),
    "Kyushu": ("Japan", "https://www.kyushu-u.ac.jp/en/admission/fees/scholarships/"),
    "Nagoya": ("Japan", "https://admissions.nagoya-u.ac.jp/en/"),
    "OsakaU": ("Japan", "https://www.osaka-u.ac.jp/en/international/inbound/scholarships"),
    "KoreaGKS": ("South Korea", "https://www.studyinkorea.go.kr/en/scholarship/gks_info.do"),
    "Turkiye": ("Turkey", "https://turkiyeburslari.gov.tr/en"),
    "EMNormandy": ("France", "https://www.em-normandie.com/en/scholarships"),
    "SKEMA": ("France", "https://www.skema.edu/programmes/scholarships"),
    "IESEG": ("France", "https://www.ieseg.fr/en/scholarships/"),
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
                entry["text"] = clean_text(soup)[:20000]
            else:
                entry["error"] = f"status {r.status_code} ({r.headers.get('Content-Type','')[:40]})"
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        results[label] = entry
        t = entry.get("title") or ""
        print(f"{label:14s} {entry['status']} {entry.get('error') or t[:60]}")
    out = OUT_DIR / "top_country_evidence4.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOutput: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
