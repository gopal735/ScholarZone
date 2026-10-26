"""Repair the catalogue's place taxonomy and coverage flags.

Dry run by default. ``--apply`` writes.

WHAT IT CHANGES, AND WHY EACH IS SAFE

``country``      Alias spellings are folded onto one canonical name. The column is
                 compared with ``==`` by near-duplicate detection, entity
                 resolution and the knowledge graph, so ``USA`` and ``United
                 States`` were two different countries to all three: the split was
                 suppressing deduplication, not just looking untidy.

``region``       Folded onto the eight-value enum in
                 ``services.taxonomy.REGIONS``. Countries used as regions and
                 sentences used as regions both go; the region is derived from the
                 canonical country, and a stored region that is already legal is
                 left exactly as the researcher set it.

``funding``      Only exact case/plural variants of the four dominant terms are
                 folded. The column is rendered verbatim on every card, so
                 collapsing descriptive labels would destroy information. The
                 rest needs a ``funding_type`` column, which is a migration.

coverage flags   ``tuition_coverage``, ``living_cost_coverage`` and
``travel_coverage`` were never backfilled, although ``official_details`` already
                 holds a clean boolean for most rows. Only genuine booleans are
                 read: a researcher sentence like "Full tuition fees for up to 4
                 years" is prose, not evidence, and is left NULL.

``fully_funded`` Set True only where tuition coverage is affirmatively True, which
                 is the invariant the research brief states. 125 rows qualify; 9
                 rows claim full funding in the JSON without a boolean tuition
                 flag and are deliberately left False.

``deletion_protected``
                 Set on archived rows only. Those rows are hidden from applicants
                 but carry the ``archived_reason`` that explains why, so they are
                 the audit trail. Every other row is already undeletable while its
                 ``verification_status`` is active, needs_review or quarantined,
                 which is the state all 722 rows are in - so blanket protection
                 would disable a designed lifecycle to guard against a risk that
                 is not currently reachable.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import taxonomy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "backend", "scholarzone.db")
REPORTS = os.path.join(ROOT, "backend", "reports")

COVERAGE_COLUMNS = ("tuition_coverage", "living_cost_coverage", "travel_coverage")


def backup_path(stamp: str) -> str:
    return os.path.join(ROOT, "backend", f"scholarzone.pre_integrity_repair_{stamp}.db")


def collect(con: sqlite3.Connection) -> list[dict]:
    """One entry per row that would change. No writes."""
    changes: list[dict] = []
    for r in con.execute(
        "select id,title,country,region,funding,tuition_coverage,living_cost_coverage,"
        "travel_coverage,fully_funded,official_details,is_archived,deletion_protected"
        " from scholarships order by id"
    ):
        sets: dict[str, object] = {}

        country = taxonomy.canonical_country(r["country"])
        if country != r["country"]:
            sets["country"] = country

        region = taxonomy.canonical_region(r["country"], r["region"])
        if region != r["region"]:
            sets["region"] = region

        funding = taxonomy.canonical_funding_label(r["funding"])
        if funding != r["funding"]:
            sets["funding"] = funding

        details: dict = {}
        if r["official_details"]:
            try:
                loaded = json.loads(r["official_details"])
                if isinstance(loaded, dict):
                    details = loaded
            except (ValueError, TypeError):
                details = {}

        for column in COVERAGE_COLUMNS:
            value = taxonomy.coverage_boolean(details.get(column))
            if value is not None and r[column] is None:
                sets[column] = value

        fully = taxonomy.coverage_boolean(details.get("fully_funded"))
        tuition = sets.get("tuition_coverage", r["tuition_coverage"])
        permitted = taxonomy.fully_funded_is_permitted(bool(fully), tuition)
        if permitted and not r["fully_funded"]:
            sets["fully_funded"] = True
        elif fully is True and not permitted and r["fully_funded"]:
            # Cannot happen on current data; kept so the invariant holds if it ever
            # does rather than being silently written through.
            sets["fully_funded"] = False

        if r["is_archived"] and not r["deletion_protected"]:
            sets["deletion_protected"] = True

        if sets:
            changes.append({"id": r["id"], "title": r["title"], "before": {
                "country": r["country"], "region": r["region"], "funding": r["funding"],
                "tuition_coverage": r["tuition_coverage"],
                "living_cost_coverage": r["living_cost_coverage"],
                "travel_coverage": r["travel_coverage"],
                "fully_funded": r["fully_funded"],
            }, "set": sets})
    return changes


def summarise(changes: list[dict]) -> dict:
    tally: dict[str, int] = {}
    for change in changes:
        for column in change["set"]:
            tally[column] = tally.get(column, 0) + 1
    return dict(sorted(tally.items(), key=lambda kv: -kv[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the changes. Without this the script only reports.")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    os.makedirs(REPORTS, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    changes = collect(con)
    tally = summarise(changes)

    print("=" * 78)
    print("INTEGRITY REPAIR PLAN" + ("" if args.apply else "   (dry run - nothing written)"))
    print("=" * 78)
    print(f"rows scanned        : {con.execute('select count(*) from scholarships').fetchone()[0]}")
    print(f"rows to change      : {len(changes)}")
    for column, n in tally.items():
        print(f"  {column:<24} {n}")

    by_column: dict[str, dict] = {}
    for change in changes:
        for column, new in change["set"].items():
            old = change["before"].get(column, "unchanged")
            by_column.setdefault(column, {}).setdefault(
                (str(old), str(new)), {"count": 0, "ids": []}
            )
            by_column[column][(str(old), str(new))]["count"] += 1
            by_column[column][(str(old), str(new))]["ids"].append(change["id"])

    for column, mapping in by_column.items():
        print()
        print(f"  {column}:")
        for (old, new), info in sorted(mapping.items(), key=lambda kv: -kv[1]["count"]):
            shown = f"{old[:70]!r} -> {new[:70]!r}"
            print(f"    {info['count']:>4}  {shown}")

    if not args.apply:
        con.close()
        print()
        print("dry run complete. Re-run with --apply to write.")
        return 0

    if not args.no_backup:
        dest = backup_path(stamp)
        con.close()
        shutil.copyfile(DB, dest)
        print()
        print(f"backup written      : {os.path.relpath(dest, ROOT)}")
        con = sqlite3.connect(DB)
        con.row_factory = sqlite3.Row

    con.execute("BEGIN")
    for change in changes:
        now = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(f"{column} = ?" for column in change["set"])
        values = list(change["set"].values()) + [now, change["id"]]
        con.execute(f"update scholarships set {assignments}, updated_at = ? where id = ?", values)
    con.commit()
    con.close()

    report = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "database": os.path.relpath(DB, ROOT),
        "rows_changed": len(changes),
        "tally": tally,
        "detail": by_column,
        "changes": changes,
    }
    out = os.path.join(REPORTS, f"integrity_repair_applied_{stamp}.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    print()
    print(f"rows updated        : {len(changes)}")
    print(f"report written      : {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())