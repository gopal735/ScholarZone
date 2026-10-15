"""Apply verified official logo candidates to scholarships missing image_url.

Reads backend/research_output/live_upcoming/logo_candidates.json (produced by
discover_official_logos.py), re-verifies the chosen logo with an HTTP HEAD,
and updates only the image_* columns. Never touches other columns.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

DB_PATH = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db")
CAND_FILE = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live_upcoming\logo_candidates_v2.json")
OUT_FILE = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live_upcoming\logo_apply_report.json")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def derive_source_type(url: str) -> str:
    d = domain_of(url)
    if ".gov" in d or "ministry" in d or "embassy" in d:
        return "official_government"
    if ".edu" in d or ".ac." in d or "university" in d or "college" in d:
        return "official_university"
    return "official_provider"


def head_ok(url: str) -> bool:
    try:
        r = requests.head(url, headers=UA, timeout=10, allow_redirects=True)
        if r.status_code in (200, 301, 302):
            return r.headers.get("Content-Type", "").startswith("image/")
        if r.status_code == 405:
            g = requests.get(url, headers=UA, timeout=15, stream=True)
            return g.status_code == 200 and g.headers.get("Content-Type", "").startswith("image/")
    except Exception:
        return False
    return False


def main() -> int:
    if not CAND_FILE.exists():
        print(f"No candidates file at {CAND_FILE}")
        return 1
    rows_data = json.loads(CAND_FILE.read_text(encoding="utf-8"))
    print(f"Loaded candidates for {len(rows_data)} rows")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    applied, failed = [], []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for entry in rows_data:
        rid = entry.get("id")
        cands = entry.get("candidates") or []
        if not rid or not cands:
            continue
        row = cur.execute("SELECT id, title, country, official_source, image_url FROM scholarships WHERE id=?", (rid,)).fetchone()
        if not row or row["image_url"]:
            continue
        chosen = None
        for c in cands:
            if head_ok(c["url"]):
                chosen = c
                break
        if not chosen:
            failed.append({"id": rid, "title": row["title"], "reason": "no candidate passed HEAD re-verification"})
            continue
        source_url = chosen.get("from_page") or chosen.get("url")
        with con:
            cur.execute(
                """UPDATE scholarships SET
                    image_url=?,
                    image_source_url=?,
                    image_source_type=?,
                    image_kind='official_logo',
                    image_alt_text=?,
                    image_verified_at=?,
                    image_evaluation_status='verified',
                    image_evaluated_at=?,
                    updated_at=?
                   WHERE id=?""",
                (
                    chosen["url"],
                    source_url,
                    derive_source_type(chosen["url"]),
                    chosen.get("alt") or row["official_source"] or row["title"],
                    now,
                    now,
                    now,
                    rid,
                ),
            )
        applied.append({"id": rid, "title": row["title"], "country": row["country"], "logo_url": chosen["url"]})
        print(f"  applied logo to id={rid} {str(row['title'])[:50]!r}")

    con.close()
    report = {"generated_at": datetime.now().isoformat(), "applied": len(applied), "failed": len(failed), "applied_records": applied, "failed_records": failed}
    OUT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nApplied {len(applied)} logos, {len(failed)} failed. Report: {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
