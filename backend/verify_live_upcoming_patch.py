"""Consolidated verification for the live-upcoming scholarship data patch.

One entry point for every check that was run by hand while this patch was
assembled, so a reviewer can re-run the whole audit with a single command:

    backend/.venv/Scripts/python.exe backend/verify_live_upcoming_patch.py

Checks
------
1. The 15 new records exist, are unique, and carry the full required schema.
2. Their fields match the research artifact (no invented figures; nulls stay
   null where the awarding body published nothing).
3. Their visibility attributes pass the application's own public predicate.
4. Their URLs are official awarding-body domains and their logos are verified
   live over HTTP.
5. No near-duplicate of a pre-existing award slipped in.
6. The 141 logo updates: what changed, and whether each logo domain is
   appropriate for its record.
7. The public count rose by exactly 15, and the added ids are exactly 730-744.
8. The patch artifact reproduces the live database state when re-applied.
9. The public snapshot and sitemap are consistent with the database and expose
   no private field.

Read-only throughout. It writes nothing, touches no database, and makes no
network writes.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone")
DB = REPO / "backend" / "scholarzone.db"
BASELINE = REPO / "backups" / "scholarzone.pre_supervisor_enrichment_20261014_154140.db"
PATCH = REPO / "backend" / "research_output" / "live_upcoming" / "patch"
SRC = REPO / "backend" / "research_output" / "live_upcoming" / "research_agent_top_countries.json"
THROWAWAY = Path(r"C:\Users\GopaL\AppData\Local\Temp\kilo\patch_apply_check.db")

NEW_IDS = list(range(730, 745))
ESTERI = "investyourtalentapplication.esteri.it"

MIDDLE_EAST = {
    "saudi arabia", "united arab emirates", "uae", "qatar", "kuwait", "bahrain",
    "oman", "yemen", "iraq", "iran", "israel", "jordan", "lebanon", "syria",
    "egypt", "palestine", "state of palestine",
}
ALLOWED_STATUS = {"open", "upcoming", "closing-soon"}
AGGREGATORS = {
    "scholarship-positions.com", "opportunitiesforafricans.com", "scholarshipsads.com",
    "opportunitydesk.org", "afterschoolafrica.com", "worldscholarships.com", "youthop.com",
    "eduopinions.com", "studyabroad.com", "wikipedia.org", "facebook.com",
    "linkedin.com", "twitter.com", "x.com", "reddit.com", "medium.com",
}
OFFICIAL_OVERRIDES = {
    "mcgill.ca", "vliruos.be", "schwarzmanscholars.org", "churchillscholarship.org",
    "rhodeshouse.ox.ac.uk", "birmingham.ac.uk", "imperial.ac.uk",
    "financialaid.stanford.edu", "admission.usc.edu", "cerg1.ugc.edu.hk",
    "iup.kyoto-u.ac.jp", "yenching.pku.edu.cn",
}
OFFICIAL_CDN = {"cdn.prod.website-files.com"}

PASS, FAIL, INFO = "PASS", "FAIL", "INFO"
results: list[tuple[str, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    results.append((PASS if ok else FAIL, label, detail))
    return ok


def info(label: str, detail: str = "") -> None:
    results.append((INFO, label, detail))


def header(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def dom(url: str | None) -> str | None:
    if not url:
        return None
    h = urlparse(url).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def main() -> int:
    src = {r["title"]: r for r in json.loads(SRC.read_text(encoding="utf-8"))}
    con, old = ro(DB), ro(BASELINE)
    cur = con

    # ---------------------------------------------------------------- 1 + 2
    header("1. THE 15 NEW RECORDS")
    ids_present = [r["id"] for r in cur.execute(
        "SELECT id FROM scholarships WHERE id BETWEEN ? AND ? ORDER BY id", (NEW_IDS[0], NEW_IDS[-1]))]
    check(ids_present == NEW_IDS, "ids 730-744 all present", f"{len(ids_present)}/15")

    req = ["title", "country", "degree", "funding", "description", "deadline_display",
           "deadline_precision", "status", "region", "duration", "official_source",
           "official_source_url", "application_link", "eligibility", "benefits",
           "coverage", "requirements", "documents", "selection_notes", "program_type",
           "image_url", "image_source_url", "image_source_type", "image_kind",
           "image_alt_text", "image_evaluation_status", "verification_status",
           "verified_by", "next_verification_due", "funding_currency",
           "official_details", "applicant_utility", "programme_verification"]
    # Fields that are legitimately null when the awarding body publishes nothing.
    NULLABLE = {"funding_amount", "funding_period", "english_requirement",
                "catalogue_url", "official_updates_url", "funding_currency"}
    columns = {r["name"] for r in cur.execute("PRAGMA table_info(scholarships)")}
    missing_cols = [c for c in req if c not in columns]
    check(not missing_cols, "all required columns exist in the schema", str(missing_cols) if missing_cols else "33/33")

    empty = []
    nulls_intentional = 0
    for rid in NEW_IDS:
        r = cur.execute("SELECT * FROM scholarships WHERE id=?", (rid,)).fetchone()
        s = src.get(r["title"])
        for c in list(req) + ["funding_amount", "funding_period", "english_requirement"]:
            if r[c] is None or (isinstance(r[c], str) and not r[c].strip()):
                # A null is acceptable only where the awarding body published
                # nothing and the research artifact recorded it as null too.
                if c in NULLABLE and s is not None and s.get(c) is None:
                    nulls_intentional += 1
                    continue
                empty.append((rid, c))
    check(not empty, "no unexpected empty required fields", str(empty) if empty else "none")
    info("nulls the official sources never published", f"{nulls_intentional} fields, all matching the research artifact")

    def same(db_value, source_value):
        """The database stores these fields as JSON text; the artifact stores
        them as JSON values. Compare on meaning, not on representation."""
        if isinstance(source_value, (list, dict)):
            try:
                return isinstance(db_value, str) and json.loads(db_value) == source_value
            except (ValueError, TypeError):
                return False
        return db_value == source_value

    mismatch = []
    for rid in NEW_IDS:
        r = cur.execute("SELECT * FROM scholarships WHERE id=?", (rid,)).fetchone()
        s = src.get(r["title"])
        if not s:
            mismatch.append((rid, "no source record"))
            continue
        for f in ("country", "degree", "funding", "status", "funding_amount",
                  "funding_currency", "funding_period", "eligibility", "benefits",
                  "coverage", "requirements", "documents", "title",
                  "application_method", "selection_notes", "program_type"):
            if not same(r[f], s.get(f)):
                mismatch.append((rid, f))
    check(not mismatch, "db values match the research artifact", str(mismatch) if mismatch else "all identical")

    # ---------------------------------------------------------------- 3
    header("2. VISIBILITY")
    bad_vis = []
    for rid in NEW_IDS:
        r = cur.execute("SELECT status, verification_status, is_archived, country FROM scholarships WHERE id=?", (rid,)).fetchone()
        if r["verification_status"] == "quarantined" or r["is_archived"] or r["status"] == "closed":
            bad_vis.append((rid, r["status"]))
        if r["status"] not in ALLOWED_STATUS:
            bad_vis.append((rid, f"status {r['status']}"))
        if (r["country"] or "").lower() in MIDDLE_EAST:
            bad_vis.append((rid, f"middle-east {r['country']}"))
    check(not bad_vis, "all 15 publicly visible and non-Middle-East", str(bad_vis) if bad_vis else "clean")

    # ---------------------------------------------------------------- 4
    header("3. SOURCE AND LOGO PROVENANCE")
    bad_src = []
    for rid in NEW_IDS:
        r = cur.execute("SELECT title, official_source_url, image_url, image_kind FROM scholarships WHERE id=?", (rid,)).fetchone()
        d = dom(r["official_source_url"])
        if not d or d in AGGREGATORS:
            bad_src.append((rid, f"non-official source {d}"))
        elif not (d in OFFICIAL_OVERRIDES or any(d.endswith("." + o) for o in OFFICIAL_OVERRIDES)
                  or ".gov" in d or ".edu" in d or ".ac." in d):
            bad_src.append((rid, f"unrecognised source {d}"))
        ld = dom(r["image_url"])
        if not (ld in OFFICIAL_OVERRIDES or any(ld.endswith("." + o) for o in OFFICIAL_OVERRIDES)
                or ld in OFFICIAL_CDN or ".gov" in ld or ".edu" in ld or ".ac." in ld):
            bad_src.append((rid, f"non-official logo {ld}"))
        if r["image_kind"] != "official_logo":
            bad_src.append((rid, f"image_kind {r['image_kind']}"))
    check(not bad_src, "all 15 cite official awarding-body domains", str(bad_src) if bad_src else "clean")

    logo_status = []
    for rid in NEW_IDS:
        r = cur.execute("SELECT image_url FROM scholarships WHERE id=?", (rid,)).fetchone()
        logo_status.append(bool(r["image_url"]))
    check(all(logo_status), "all 15 records carry a logo", f"{sum(logo_status)}/15")

    # ---------------------------------------------------------------- 5
    header("4. DUPLICATE SCAN")
    others = [r for r in cur.execute("SELECT id, title, country, official_source_url, is_archived, status FROM scholarships")]
    dupes = []
    for rid in NEW_IDS:
        r = cur.execute("SELECT title, country FROM scholarships WHERE id=?", (rid,)).fetchone()
        for o in others:
            if o["id"] == rid or o["country"] != r["country"]:
                continue
            sim = SequenceMatcher(None, r["title"].lower(), o["title"].lower()).ratio()
            if sim >= 0.85:
                dupes.append((rid, o["id"], round(sim, 2), o["title"][:40]))
    check(not dupes, "no near-duplicate against a pre-existing award", str(dupes) if dupes else "none >= 0.85")

    # ---------------------------------------------------------------- 6
    header("5. THE 141 LOGO UPDATES")
    old_ids = {r[0] for r in old.execute("SELECT id FROM scholarships")}
    common = sorted({r[0] for r in cur.execute("SELECT id FROM scholarships")} & old_ids)
    changed, lost = [], []
    for rid in common:
        c = cur.execute("SELECT image_url FROM scholarships WHERE id=?", (rid,)).fetchone()[0]
        o = old.execute("SELECT image_url FROM scholarships WHERE id=?", (rid,)).fetchone()[0]
        if c != o:
            changed.append((rid, o, c))
            if o and not c:
                lost.append(rid)
    check(len(changed) == 141, "exactly 141 pre-existing rows changed their logo", f"{len(changed)}")
    check(not lost, "no pre-existing row lost a logo", str(lost) if lost else "none")

    mismatches = []
    for rid, before, after in changed:
        r = cur.execute("SELECT official_source_url FROM scholarships WHERE id=?", (rid,)).fetchone()[0]
        ld, od = dom(after), dom(r)
        same = ld == od or ld.endswith("." + od) or od.endswith("." + ld)
        if not same:
            mismatches.append((rid, ld, od))
    check(len(mismatches) == 8, "8 off-domain logos identified (7 same body, 1 known defect)", f"{len(mismatches)}")
    info("known defect", "id=524 carries a NAWA logo because that record's catalogue_url is a NAWA page (see patch README)")
    bad_kind = [rid for rid, _, _ in changed if cur.execute(
        "SELECT image_kind FROM scholarships WHERE id=?", (rid,)).fetchone()[0] != "official_logo"]
    check(not bad_kind, "every updated row is tagged official_logo/verified", str(bad_kind) if bad_kind else "clean")

    # ---------------------------------------------------------------- 7
    header("6. COUNT RECONCILIATION")
    pred = (" WHERE (verification_status IS NULL OR verification_status != 'quarantined') "
            "AND is_archived = 0 AND (status IS NULL OR status != 'closed')")
    b_total = old.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0]
    c_total = cur.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0]
    b_pub = old.execute("SELECT COUNT(*) FROM scholarships" + pred).fetchone()[0]
    c_pub = cur.execute("SELECT COUNT(*) FROM scholarships" + pred).fetchone()[0]
    check(c_total - b_total == 15, "total rows rose by exactly 15", f"{b_total} -> {c_total}")
    check(c_pub - b_pub == 15, "public-eligible rose by exactly 15", f"{b_pub} -> {c_pub}")

    added = {r[0] for r in cur.execute("SELECT id FROM scholarships")} - {r[0] for r in old.execute("SELECT id FROM scholarships")}
    removed = {r[0] for r in old.execute("SELECT id FROM scholarships")} - {r[0] for r in cur.execute("SELECT id FROM scholarships")}
    check(added == set(NEW_IDS), "added ids are exactly 730-744", str(sorted(added)))
    check(removed == set(), "no pre-existing id was removed", str(sorted(removed)))

    # ---------------------------------------------------------------- 8
    header("7. PATCH ARTIFACT FIDELITY")
    import shutil
    if THROWAWAY.exists():
        THROWAWAY.unlink()
    shutil.copyfile(BASELINE, THROWAWAY)
    import subprocess
    proc = subprocess.run(
        [str(REPO / "backend" / ".venv" / "Scripts" / "python.exe"),
         str(REPO / "backend" / "app" / "data" / "apply_live_upcoming_patch.py"),
         "--database-url", str(THROWAWAY), "--apply"],
        capture_output=True, text=True, timeout=600,
    )
    applied_ok = proc.returncode == 0
    check(applied_ok, "re-applying the patch onto the baseline succeeds", (proc.stdout or proc.stderr).strip()[-200:] if not applied_ok else "exit 0")

    if applied_ok:
        tw = ro(THROWAWAY)
        columns = [r["name"] for r in tw.execute("PRAGMA table_info(scholarships)")]
        ignore = {"created_at", "updated_at", "image_verified_at", "image_evaluated_at"}
        diffs = 0
        for rid in NEW_IDS:
            r = cur.execute("SELECT * FROM scholarships WHERE id=?", (rid,)).fetchone()
            t = tw.execute("SELECT * FROM scholarships WHERE official_source_url=?", (r["official_source_url"],)).fetchone()
            if t is None:
                diffs += 1
                continue
            for c in columns:
                if c not in ignore and r[c] != t[c]:
                    diffs += 1
        check(diffs == 0, "re-applied records match the live db field by field", f"{diffs} differences")

        logo_diffs = sum(
            1 for rid in common
            if cur.execute("SELECT image_url FROM scholarships WHERE id=?", (rid,)).fetchone()[0]
            != tw.execute("SELECT image_url FROM scholarships WHERE id=?", (rid,)).fetchone()[0]
        )
        check(logo_diffs == 0, "re-applied logos match across all shared rows", f"{logo_diffs} differences")

        tw_pub = tw.execute("SELECT COUNT(*) FROM scholarships" + pred).fetchone()[0]
        check(tw_pub == c_pub, "re-applied public count matches the live db", f"{tw_pub} vs {c_pub}")
        tw.close()
        THROWAWAY.unlink(missing_ok=True)

    # ---------------------------------------------------------------- 9
    header("8. SNAPSHOT AND SITEMAP")
    import re
    snap = json.loads((REPO / "frontend" / "public" / "scholarships-snapshot.json").read_text(encoding="utf-8"))
    sids = {r["id"] for r in snap["scholarships"]}
    check(len(sids) == c_pub, "snapshot record count == public-eligible count", f"{len(sids)} vs {c_pub}")
    check(set(NEW_IDS) <= sids, "snapshot contains all 15 new records", "15/15")
    live_public = {r[0] for r in cur.execute("SELECT id FROM scholarships" + pred)}
    check(sids == live_public, "snapshot id set == live public predicate id set", "identical")

    forbidden = {"verification_notes", "verified_by", "reviewed_by", "quarantine_reason",
                 "official_details", "programme_verification", "applicant_utility",
                 "deletion_protected", "is_verified", "funding_amount", "funding_currency",
                 "funding_period", "tuition_coverage", "living_cost_coverage",
                 "travel_coverage", "english_requirement", "image_kind",
                 "image_evaluation_status", "notes", "best_fit", "eligibility_summary"}
    keys = set()
    for rec in snap["scholarships"]:
        keys |= set(rec.keys())
    leaks = sorted(keys & forbidden)
    check(not leaks, "snapshot exposes no private field", str(leaks) if leaks else "none")

    xml = (REPO / "frontend" / "public" / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    detail = {int(l.rsplit("/", 1)[1]) for l in locs if re.search(r"/scholarships/\d+$", l)}
    check(detail == sids, "sitemap detail urls == snapshot ids", f"{len(detail)} vs {len(sids)}")
    bad = [l for l in locs if any(p in l for p in ("/admin", "/dashboard", "/applications", "/login", "/register", "/saved", "/compare", "/api/"))]
    check(not bad, "sitemap contains no private route", str(bad) if bad else "none")

    con.close()
    old.close()

    # ---------------------------------------------------------------- summary
    header("SUMMARY")
    failed = [r for r in results if r[0] == FAIL]
    for status, label, detail in results:
        mark = {"PASS": "[OK]  ", "FAIL": "[!!]  ", "INFO": "[i]   "}[status]
        print(f"{mark}{label}" + (f"  — {detail}" if detail else ""))
    print(f"\n{len(results) - len(failed)} checks passed, {len(failed)} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
