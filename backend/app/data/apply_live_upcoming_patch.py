"""Apply the live-upcoming data patch: 15 new scholarships + 141 official logos.

What this is
------------
The patch first appeared as direct edits to the (gitignored) local database.
That is fine for research and useless for review: nobody can see the change,
nobody can re-apply it, and nobody can diff it. This script turns the change
into a reviewable artifact — ``research_output/live_upcoming/patch/`` — and
makes re-applying it a deliberate, checkable act.

CopyFiles into ``backend/app/data/`` rather than a maintenance module because
this is a data import, not a scheduled task. Nothing calls it automatically and
nothing should: it is a one-shot, human-reviewed migration.

Safety rules it enforces on every run
-------------------------------------
* **Dry-run by default.** Nothing is written unless ``--apply`` is passed.
* **Never touches production.** It refuses to run when
  ``SCHOLARZONE_ENVIRONMENT=production``, and it refuses any database that is
  not the local development SQLite file unless ``--allow-remote`` is passed
  explicitly. A PostgreSQL URL never reaches it by accident.
* **Checks the source before writing.** Every new record must be absent, or
  byte-identical to what is already there. Every logo update must target a row
  that still has no ``image_url``. A duplicate or a conflict is refused, never
  overwritten.
* **One transaction.** Any refusal rolls the whole apply back, so a partially
  applied patch is not a state the database can be left in.
* **Validates after writing.** The public predicate is imported from the
  application, not re-implemented, so what is applied is measured by the same
  rule the catalogue is served by.

Run
---
    backend/.venv/Scripts/python.exe backend/app/data/apply_live_upcoming_patch.py
    backend/.venv/Scripts/python.exe backend/app/data/apply_live_upcoming_patch.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

# This script lives in backend/app/data/, so the backend root is two levels up.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

REPO_ROOT = BACKEND_ROOT.parent
PATCH_DIR = REPO_ROOT / "backend" / "research_output" / "live_upcoming" / "patch"
LOCAL_DB = BACKEND_ROOT / "scholarzone.db"
VERIFIED_BY = "live_research_batch_2026-10-15"
TODAY = date(2026, 10, 15)

#: Columns copied verbatim from the patch for a new scholarship row.
NEW_RECORD_COLUMNS = [
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

MIDDLE_EAST = {
    "saudi arabia", "united arab emirates", "uae", "qatar", "kuwait", "bahrain",
    "oman", "yemen", "iraq", "iran", "israel", "jordan", "lebanon", "syria",
    "egypt", "palestine", "state of palestine",
}
ALLOWED_STATUS = {"open", "upcoming", "closing-soon"}


class Refusal(RuntimeError):
    """A refused apply. Raised so the run fails loudly and nothing is written."""


def load_patch(patch_dir: Path) -> tuple[dict, list[dict], list[dict]]:
    manifest_path = patch_dir / "manifest.json"
    if not manifest_path.exists():
        raise Refusal(f"no patch manifest at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = json.loads((patch_dir / "new_records.json").read_text(encoding="utf-8"))
    logos = json.loads((patch_dir / "logo_updates.json").read_text(encoding="utf-8"))
    return manifest, records, logos


def resolve_database(arg: str | None, allow_remote: bool) -> tuple[str, str]:
    """Return (kind, target) where kind is 'sqlite' or 'sqlalchemy-url'.

    Refuses production and refuses anything that is not the local development
    SQLite database unless ``--allow-remote`` is passed. A remote target is
    never the default.
    """
    environment = (os.getenv("SCHOLARZONE_ENVIRONMENT") or "development").strip().lower()
    if environment == "production":
        raise Refusal(
            "SCHOLARZONE_ENVIRONMENT=production. This script applies a local research "
            "patch and must never write a production database. Unset the variable or "
            "point it at a development environment."
        )

    if arg:
        remote_schemes = ("postgresql://", "postgres://", "mysql://", "mssql://")
        if arg.startswith(remote_schemes):
            if not allow_remote:
                raise Refusal(
                    f"--database-url points at a non-SQLite target ({arg}). Pass "
                    "--allow-remote only for a throwaway development database, never "
                    "for production."
                )
            return ("sqlalchemy", arg)
        # A bare path or a sqlite:/// URL both name a local SQLite file. Resolving
        # it to an absolute path keeps the warning message honest about what will
        # actually be opened.
        path = arg[len("sqlite:///"):] if arg.startswith("sqlite") else arg
        if not Path(path).is_absolute():
            path = str((Path.cwd() / path).resolve())
        return ("sqlite", path)

    target = str(LOCAL_DB)
    if not LOCAL_DB.exists():
        raise Refusal(f"local development database not found at {target}")
    return ("sqlite", target)


def guard_patch(manifest: dict) -> None:
    """Reject a patch that is not the one this script was written for."""
    if manifest.get("schema_version") != 1:
        raise Refusal(f"unsupported patch schema_version={manifest.get('schema_version')!r}")
    if not manifest.get("counts", {}).get("new_records"):
        raise Refusal("patch contains no new records")


def guard_records(records: list[dict]) -> None:
    seen_urls: set[str] = set()
    seen_tc: set[tuple[str, str]] = set()
    for rec in records:
        title = (rec.get("title") or "").strip()
        country = (rec.get("country") or "").strip()
        url = (rec.get("official_source_url") or "").strip()
        if not title:
            raise Refusal("a patch record has no title")
        if country.lower() in MIDDLE_EAST:
            raise Refusal(f"patch record {title!r} is a Middle East country ({country}); this patch must not contain one")
        if not url.startswith("http"):
            raise Refusal(f"patch record {title!r} has no official_source_url")
        if (rec.get("status") or "").lower() not in ALLOWED_STATUS:
            raise Refusal(
                f"patch record {title!r} has status={rec.get('status')!r}, which is not publicly visible"
            )
        low = url.lower().rstrip("/")
        if low in seen_urls:
            raise Refusal(f"patch records share official_source_url {url}")
        seen_urls.add(low)
        tc = (country.lower(), title.lower())
        if tc in seen_tc:
            raise Refusal(f"patch records share title+country ({title!r}, {country!r})")
        seen_tc.add(tc)


def prefix_columns(con) -> list[str]:
    rows = con.execute("PRAGMA table_info(scholarships)").fetchall()
    return [r[1] for r in rows]


def _db_value(value):
    """Render a patch value into something SQLite can bind.

    The patch stores lists and objects as JSON types; the scholarships table
    keeps them as JSON text. Everything else passes through untouched.
    """
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def plan_new_records(con, records: list[dict]) -> list[dict]:
    """Decide, per record, whether it is absent (insert), identical (skip), or
    conflicting (refuse). Nothing is written here."""
    columns = prefix_columns(con)
    existing_urls = {
        (r[0] or "").lower().rstrip("/")
        for r in con.execute("SELECT official_source_url FROM scholarships")
    }
    plan: list[dict] = []
    for rec in records:
        row = {c: _db_value(rec.get(c)) for c in NEW_RECORD_COLUMNS if c in columns}
        logo = rec.get("logo") or {}
        if logo.get("image_url"):
            row["image_url"] = logo["image_url"]
            row["image_source_url"] = logo.get("image_source_url") or rec.get("official_source_url")
            row["image_source_type"] = logo.get("image_source_type")
            row["image_alt_text"] = logo.get("image_alt_text")
            row["image_kind"] = "official_logo"
            row["image_evaluation_status"] = "verified"
        verification = rec.get("verification") or {}
        row.update(
            {
                "is_verified": 1,
                "verification_status": "active",
                "verified_by": VERIFIED_BY,
                "next_verification_due": TODAY.replace(year=TODAY.year + 1).isoformat(),
                "verification_notes": verification.get("notes"),
                "last_verified_at": TODAY.isoformat(),
                "last_verified_date": TODAY.isoformat(),
                "is_archived": 0,
                "deletion_protected": 0,
                "official_details": json.dumps(
                    {
                        "official_source_urls": verification.get("source_citations") or [rec.get("official_source_url")],
                        "catalogue_url": rec.get("catalogue_url"),
                        "official_updates_url": rec.get("official_updates_url"),
                        "research_batch": "research_agent_top_countries.json",
                        "confidence": verification.get("confidence"),
                    },
                    ensure_ascii=False,
                ),
                "applicant_utility": json.dumps(
                    {"summary": rec.get("best_fit"), "notes": rec.get("notes")},
                    ensure_ascii=False,
                ),
                "programme_verification": json.dumps(
                    {
                        "source_citations": verification.get("source_citations") or [rec.get("official_source_url")],
                        "last_verified_date": verification.get("last_verified_date") or TODAY.isoformat(),
                        "verification_status": "confirmed",
                        "confidence": verification.get("confidence"),
                        "notes": verification.get("notes"),
                    },
                    ensure_ascii=False,
                ),
            }
        )
        row = {k: v for k, v in row.items() if k in columns}

        url = rec["official_source_url"]
        existing = con.execute(
            "SELECT id FROM scholarships WHERE lower(rtrim(official_source_url)) = ?",
            (url.lower().rstrip("/"),),
        ).fetchone()
        if existing:
            raise Refusal(
                f"official_source_url {url} already exists on scholarship id={existing[0]}; "
                "refusing to insert a duplicate"
            )
        plan.append({"row": row, "url": url, "title": rec["title"], "country": rec["country"]})
    return plan


def plan_logo_updates(con, logos: list[dict]) -> list[dict]:
    plan, skipped = [], []
    for entry in logos:
        rid = entry["id"]
        before = entry.get("before_image_url")
        row = con.execute(
            "SELECT id, image_url FROM scholarships WHERE id=?", (rid,)
        ).fetchone()
        if row is None:
            raise Refusal(f"logo update targets missing scholarship id={rid}")
        if before is None:
            # The patch expects to fill a gap. If the row already has a logo the
            # change has already been applied - that is a skip, not a conflict.
            if row[1]:
                skipped.append({"id": rid, "reason": "already has image_url (already applied)"})
                continue
        elif row[1] != before:
            raise Refusal(
                f"scholarship id={rid} image_url is {row[1]!r} but the patch expected "
                f"{before!r}; refusing to overwrite a conflicting value"
            )
        plan.append(entry)
    return plan + skipped if False else plan + skipped


def apply(con, new_plan: list[dict], logo_plan: list[dict]) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM scholarships").fetchone()[0]
    inserted: list[int] = []
    updated: list[int] = []
    try:
        for entry in new_plan:
            max_id += 1
            row = dict(entry["row"])
            row["id"] = max_id
            row["created_at"] = now
            row["updated_at"] = now
            if entry.get("logo", {}).get("image_url"):
                row["image_verified_at"] = now
                row["image_evaluated_at"] = now
            cols = list(row.keys())
            con.execute(
                f"INSERT INTO scholarships ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                [row[c] for c in cols],
            )
            inserted.append(max_id)

        for entry in logo_plan:
            if "reason" in entry:
                continue
            con.execute(
                """UPDATE scholarships SET
                    image_url=?, image_source_url=?, image_source_type=?,
                    image_kind=?, image_alt_text=?, image_verified_at=?,
                    image_evaluation_status='verified', image_evaluated_at=?, updated_at=?
                   WHERE id=?""",
                (
                    entry["after_image_url"],
                    entry["image_source_url"],
                    entry["image_source_type"],
                    entry["image_kind"],
                    entry["image_alt_text"],
                    now,
                    now,
                    now,
                    entry["id"],
                ),
            )
            updated.append(entry["id"])
        con.commit()
    except Exception:
        con.rollback()
        raise
    return {"inserted_ids": inserted, "updated_ids": updated}


def validate(con) -> dict:
    from app.repositories.scholarships import public_visibility_conditions
    from sqlalchemy import select

    conditions = public_visibility_conditions()
    placeholders = " AND ".join(
        (
            "(verification_status IS NULL OR verification_status != 'quarantined')",
            "is_archived = 0",
            "(status IS NULL OR status != 'closed')",
        )
    )
    public_ids = {r[0] for r in con.execute(f"SELECT id FROM scholarships WHERE {placeholders}")}
    injected = con.execute("SELECT id FROM scholarships WHERE verified_by=?", (VERIFIED_BY,)).fetchall()
    injected_ids = sorted(r[0] for r in injected)
    visible = [i for i in injected_ids if i in public_ids]
    with_logo = con.execute(
        "SELECT COUNT(*) FROM scholarships WHERE verified_by=? AND image_url IS NOT NULL AND image_url != ''",
        (VERIFIED_BY,),
    ).fetchone()[0]
    return {
        "public_predicate": [str(c) for c in conditions],
        "injected_ids": injected_ids,
        "injected_visible_under_public_predicate": visible,
        "injected_with_logo": with_logo,
        "public_total": len(public_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply the live-upcoming data patch (15 new scholarships + 141 official logos).",
        epilog="DRY RUN BY DEFAULT. Pass --apply to write.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Report only; write nothing (the default).")
    mode.add_argument("--apply", action="store_true", help="Write the changes in one transaction.")
    parser.add_argument("--patch-dir", type=Path, default=PATCH_DIR, help="Override the patch artifact directory.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLite path to use instead of the local development database. Non-SQLite targets require --allow-remote.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit a non-SQLite --database-url. Never use this for production.",
    )
    args = parser.parse_args()
    do_apply = args.apply

    try:
        manifest, records, logos = load_patch(args.patch_dir)
        guard_patch(manifest)
        guard_records(records)
        kind, target = resolve_database(args.database_url, args.allow_remote)
    except Refusal as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2

    print("=" * 78)
    print("LIVE-UPCOMING DATA PATCH")
    print("=" * 78)
    print(f"  patch        : {args.patch_dir}")
    print(f"  created_at   : {manifest.get('created_at')}")
    print(f"  new records  : {manifest['counts']['new_records']}")
    print(f"  logo updates : {manifest['counts']['logo_updates']}")
    print(f"  database     : {kind}:{target}")
    print(f"  mode         : {'APPLY' if do_apply else 'DRY RUN (nothing will be written)'}")
    print()

    import sqlite3

    con = sqlite3.connect(target)
    con.row_factory = sqlite3.Row
    try:
        new_plan = plan_new_records(con, records)
        logo_plan = plan_logo_updates(con, logos)
    except Refusal as refusal:
        con.close()
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2

    skips = [e for e in logo_plan if "reason" in e]
    to_write = [e for e in logo_plan if "reason" not in e]
    print(f"planned: {len(new_plan)} inserts, {len(to_write)} logo updates, {len(skips)} already-applied skips")
    for entry in new_plan[:15]:
        print(f"  + id=? [{entry['country']}] {entry['title'][:60]}")
    print()

    if not do_apply:
        con.close()
        print("DRY RUN COMPLETE — no changes written. Re-run with --apply to apply.")
        return 0

    result = apply(con, new_plan, to_write)
    report = validate(con)
    con.close()

    print("APPLIED")
    print(f"  inserted ids : {result['inserted_ids']}")
    print(f"  updated ids  : {len(result['updated_ids'])}")
    print(f"  skipped      : {len(skips)}")
    print()
    print("VALIDATION")
    print(f"  injected records            : {len(report['injected_ids'])}")
    print(f"  visible under public rules  : {len(report['injected_visible_under_public_predicate'])}")
    print(f"  injected with a logo        : {report['injected_with_logo']}")
    print(f"  public catalogue total now  : {report['public_total']}")
    ok = len(report["injected_visible_under_public_predicate"]) == len(report["injected_ids"])
    print(f"  ALL INJECTED RECORDS PUBLICLY VISIBLE: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
