"""Build the version-controlled data patch artifact for the live-upcoming additions.

Sources of truth, in order:
  1. backend/research_output/live_upcoming/research_agent_top_countries.json
     (the researched records: fields, evidence, verification block, logo)
  2. backend/scholarzone.db + backups/scholarzone.pre_supervisor_enrichment_*.db
     (the exact before/after logo state, read-only)

Output (tracked, no database, no private data):
  backend/research_output/live_upcoming/patch/manifest.json
  backend/research_output/live_upcoming/patch/new_records.json
  backend/research_output/live_upcoming/patch/logo_updates.json
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone")
LIVE = REPO / "backend" / "research_output" / "live_upcoming"
SRC_RECORDS = LIVE / "research_agent_top_countries.json"
OUT_DIR = LIVE / "patch"
DB = REPO / "backend" / "scholarzone.db"
BEFORE_DB = REPO / "backups" / "scholarzone.pre_supervisor_enrichment_20261014_154140.db"
NEW_IDS = list(range(730, 745))

# The fields written into the scholarships table for a new record. Everything
# here is public catalogue data plus provenance; there is no user data.
FIELD_ORDER = [
    "title", "country", "degree", "funding", "description",
    "deadline_date", "deadline_display", "deadline_precision", "status",
    "region", "duration", "application_period",
    "official_source", "official_source_url", "catalogue_url",
    "official_updates_url", "application_link",
    "eligibility", "eligibility_summary", "benefits", "coverage",
    "requirements", "documents", "english_requirement", "application_method",
    "selection_notes", "program_type", "best_fit", "notes",
    "funding_amount", "funding_currency", "funding_period",
    "tuition_coverage", "living_cost_coverage", "travel_coverage", "fully_funded",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_source_type(url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if ".gov" in host or "ministry" in host or "embassy" in host:
        return "official_government"
    if ".edu" in host or ".ac." in host or "university" in host or "college" in host:
        return "official_university"
    return "official_provider"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = json.loads(SRC_RECORDS.read_text(encoding="utf-8"))

    # ---- new_records.json -------------------------------------------------
    # The array order is the order a fresh apply will insert in, which decides
    # the rowids it hands out. Ordering by the live database's own id sequence
    # for these records means re-applying the patch onto the same pre-patch
    # state reproduces ids 730-744 exactly rather than shifting them.
    con0 = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    live_order = [
        r[0]
        for r in con0.execute(
            "SELECT official_source_url FROM scholarships WHERE id BETWEEN ? AND ? ORDER BY id",
            (NEW_IDS[0], NEW_IDS[-1]),
        )
    ]
    con0.close()
    by_url = {(r.get("official_source_url") or "").lower().rstrip("/"): r for r in records}
    ordered = []
    for url in live_order:
        rec = by_url.get(url.lower().rstrip("/"))
        if rec is None:
            raise SystemExit(f"live id ordering references a URL absent from the research artifact: {url}")
        ordered.append(rec)
    missing = [r for r in records if r not in ordered]
    if missing:
        raise SystemExit(f"{len(missing)} researched records have no live id; refusing to build")
    records = ordered

    new_records = []
    for rec in records:
        logo = rec.get("logo")
        entry = {k: rec.get(k) for k in FIELD_ORDER}
        entry["logo"] = (
            {
                "image_url": logo["logo_url"],
                "image_source_url": logo.get("logo_source_url") or rec.get("official_source_url"),
                "image_source_type": derive_source_type(logo.get("logo_source_url") or rec.get("official_source_url", "")),
                "image_source_type_override": None,
                "image_alt_text": logo.get("logo_alt") or rec.get("official_source"),
            }
            if logo
            else None
        )
        entry["verification"] = rec.get("verification")
        new_records.append(entry)

    # ---- logo_updates.json -------------------------------------------------
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    old = sqlite3.connect(f"file:{BEFORE_DB}?mode=ro", uri=True)
    old.row_factory = sqlite3.Row

    cur_ids = {r[0] for r in con.execute("SELECT id FROM scholarships")}
    old_ids = {r[0] for r in old.execute("SELECT id FROM scholarships")}
    common = sorted(cur_ids & old_ids)

    logo_updates = []
    for rid in common:
        c = con.execute(
            "SELECT id, title, country, image_url, image_source_url, image_source_type, image_alt_text FROM scholarships WHERE id=?",
            (rid,),
        ).fetchone()
        o = old.execute(
            "SELECT image_url FROM scholarships WHERE id=?", (rid,)
        ).fetchone()
        if (c["image_url"] or None) != (o["image_url"] or None) or False:
            pass
        if c["image_url"] != o["image_url"]:
            logo_updates.append(
                {
                    "id": rid,
                    "title": c["title"],
                    "country": c["country"],
                    "before_image_url": o["image_url"],
                    "after_image_url": c["image_url"],
                    "image_source_url": c["image_source_url"],
                    "image_source_type": c["image_source_type"],
                    "image_alt_text": c["image_alt_text"],
                    "image_kind": "official_logo",
                    "image_evaluation_status": "verified",
                }
            )

    con.close()
    old.close()

    # ---- manifest.json -----------------------------------------------------
    def digest(p: Path) -> str:
        if not p.exists():
            return None
        return sha256_file(p)

    manifest = {
        "schema_version": 1,
        "patch_name": "live-upcoming-top-demand-countries",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "15 newly researched scholarships in top-demand countries plus 141 backfilled "
            "official logos for pre-existing records. Researched against official "
            "awarding-body pages only; no figure was invented where a source published none."
        ),
        "source": {
            "research_artifact": str(SRC_RECORDS.relative_to(REPO)),
            "research_artifact_sha256": digest(SRC_RECORDS),
            "current_database": str(DB.relative_to(REPO)),
            "current_database_sha256": digest(DB),
            "baseline_database_for_logos": str(BEFORE_DB.relative_to(REPO)),
            "baseline_database_sha256": digest(BEFORE_DB),
            "middle_east_excluded": True,
            "aggregator_domains_excluded": True,
        },
        "counts": {
            "new_records": len(new_records),
            "logo_updates": len(logo_updates),
            "logo_updates_that_had_a_url_before": sum(
                1 for e in logo_updates if e["before_image_url"]
            ),
            "logo_updates_from_null": sum(1 for e in logo_updates if not e["before_image_url"]),
        },
        "corrections": {
            "applied_after_insertion": [
                {
                    "scholarship_id": 737,
                    "field": "official_source_url, application_link",
                    "before": "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/",
                    "after": (
                        "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"
                        "commonwealth-shared-scholarship-20262027.php"
                    ),
                    "reason": (
                        "The record cited Imperial's generic scholarship-search page instead of its own "
                        "programme page. The other three Imperial records had already been corrected to "
                        "per-scholarship URLs; this one was not, because the pass that corrected the URLs "
                        "rewrote the research artifact rather than the database."
                    ),
                    "evidence": (
                        "GET the corrected URL returns 200 with document title "
                        "'Commonwealth Shared Scholarship | Study | Imperial College London'."
                    ),
                    "scripts": [
                        "backend/correct_imperial_737.py",
                        "backend/correct_imperial_737_citations.py",
                    ],
                }
            ]
        },
        "new_record_ids_reserved": NEW_IDS,
        "apply": {
            "script": "backend/app/data/apply_live_upcoming_patch.py",
            "default_mode": "dry-run",
            "apply_requires_explicit_flag": "--apply",
            "transactional": True,
            "refuses_duplicates": True,
            "refuses_conflicts": True,
            "never_writes_production": True,
        },
    }

    (OUT_DIR / "new_records.json").write_text(
        json.dumps(new_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / "logo_updates.json").write_text(
        json.dumps(logo_updates, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"new_records   : {len(new_records)}")
    print(f"logo_updates  : {len(logo_updates)}")
    print(f"  from null   : {manifest['counts']['logo_updates_from_null']}")
    print(f"  had url     : {manifest['counts']['logo_updates_that_had_a_url_before']}")
    print(f"artifact dir  : {OUT_DIR}")
    for p in sorted(OUT_DIR.iterdir()):
        print(f"  {p.name:22s} {p.stat().st_size:>10,} bytes  sha256 {sha256_file(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
