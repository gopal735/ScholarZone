"""Wave-4 preflight audit.

Read-only. Reports the true state of the catalogue so the next research wave is
scoped against evidence instead of assumption.
"""

from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import taxonomy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "backend", "scholarzone.db")

#: The region enum lives in services.taxonomy and nowhere else. A second copy
#: here drifts from the list the repair actually writes and then reports the
#: repaired data as a violation of a vocabulary nothing else uses.
REGIONS = set(taxonomy.REGIONS)
ISO = {
    "Australia",
    "United States",
    "Canada",
    "New Zealand",
    "United Kingdom",
    "Ireland",
    "France",
    "Germany",
    "Netherlands",
    "Belgium",
    "Switzerland",
    "Austria",
    "Sweden",
    "Norway",
    "Denmark",
    "Finland",
    "Iceland",
    "Italy",
    "Spain",
    "Portugal",
    "Greece",
    "Czech Republic",
    "Czechia",
    "Poland",
    "Hungary",
    "Romania",
    "Bulgaria",
    "Croatia",
    "Slovakia",
    "Slovenia",
    "Estonia",
    "Latvia",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Cyprus",
    "Serbia",
    "Ukraine",
    "Türkiye",
    "Turkiye",
    "Japan",
    "South Korea",
    "China",
    "India",
    "Indonesia",
    "Malaysia",
    "Thailand",
    "Vietnam",
    "Singapore",
    "Philippines",
    "Hong Kong",
    "Taiwan",
    "Pakistan",
    "Bangladesh",
    "Sri Lanka",
    "Nepal",
    "Brazil",
    "Mexico",
    "Argentina",
    "Chile",
    "Colombia",
    "Peru",
    "Costa Rica",
    "Panama",
    "Cuba",
    "Uruguay",
    "South Africa",
    "Nigeria",
    "Ghana",
    "Kenya",
    "Ethiopia",
    "Tanzania",
    "Uganda",
    "Egypt",
    "Morocco",
    "Tunisia",
    "Senegal",
    "Zimbabwe",
    "Zambia",
    "Rwanda",
    "Botswana",
    "Namibia",
    "Mauritius",
    "Israel",
    "United Arab Emirates",
    "Saudi Arabia",
    "Qatar",
    "Kuwait",
    "Jordan",
    "Lebanon",
    "Oman",
    "Bahrain",
    "Iraq",
    "Iran",
    "Georgia",
    "Armenia",
    "Azerbaijan",
    "Kazakhstan",
    "Uzbekistan",
    "Global",
    "Worldwide",
    "Multiple",
}


def rule(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def load_json(path: str):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except Exception:
        return None


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    q = lambda s, *a: con.execute(s, a).fetchall()

    rule("1. CATALOGUE SIZE")
    total = q("select count(*) n from scholarships")[0]["n"]
    print(f"total rows: {total}")
    for r in q(
        "select status, count(*) n from scholarships group by 1 order by n desc"
    ):
        print(f"  status={r['status']:<14} {r['n']}")
    for r in q(
        "select verification_status, count(*) n from scholarships group by 1 order by n desc"
    ):
        print(f"  verification_status={str(r['verification_status']):<14} {r['n']}")
    for r in q("select is_archived, count(*) n from scholarships group by 1"):
        print(f"  is_archived={r['is_archived']:<14} {r['n']}")
    for r in q("select is_verified, count(*) n from scholarships group by 1"):
        print(f"  is_verified={r['is_verified']:<14} {r['n']}")
    print(
        "  deletion_protected:",
        q("select count(*) n from scholarships where deletion_protected=1")[0]["n"],
        "protected /",
        total,
    )

    rule("2. FIELD COMPLETENESS (card-relevant)")
    checks = [
        ("image_url", "{c} is not null and {c} <> ''"),
        ("official_source_url", "{c} is not null and {c} <> ''"),
        ("catalogue_url", "{c} is not null and {c} <> ''"),
        ("application_link", "{c} is not null and {c} <> ''"),
        ("deadline_date", "{c} is not null and {c} <> ''"),
        ("deadline_display", "{c} is not null and {c} <> ''"),
        ("application_period", "{c} is not null and {c} <> ''"),
        ("funding_amount", "{c} is not null"),
        ("funding_currency", "{c} is not null and {c} <> ''"),
        ("tuition_coverage", "{c} is not null"),
        ("fully_funded", "{c} is not null"),
        ("duration", "{c} is not null and {c} <> ''"),
        ("region", "{c} is not null and {c} <> ''"),
        ("degree", "{c} is not null and {c} <> ''"),
        ("funding", "{c} is not null and {c} <> ''"),
        ("eligibility_summary", "{c} is not null and {c} <> ''"),
        ("coverage", "{c} is not null and {c} <> ''"),
        ("benefits", "{c} is not null and {c} <> ''"),
        ("requirements", "{c} is not null and {c} <> ''"),
        ("documents", "{c} is not null and {c} <> ''"),
        ("application_method", "{c} is not null and {c} <> ''"),
        ("program_type", "{c} is not null and {c} <> ''"),
        ("official_details", "{c} is not null"),
        ("applicant_utility", "{c} is not null"),
        ("programme_verification", "{c} is not null"),
        ("selection_notes", "{c} is not null and {c} <> ''"),
        ("english_requirement", "{c} is not null and {c} <> ''"),
        ("best_fit", "{c} is not null and {c} <> ''"),
    ]
    for col, cond in checks:
        pred = cond.replace("{c}", col)
        have = q(f"select count(*) n from scholarships where {pred}")[0]["n"]
        pct = 100.0 * have / total
        bar = "#" * int(pct / 2.5)
        print(f"  {col:<26} {have:>4}/{total}  {pct:5.1f}%  {bar}")

    rule("2b. FUNDING INVARIANT (fully_funded requires tuition_coverage)")
    violation = q(
        "select id,title,fully_funded,tuition_coverage from scholarships"
        " where fully_funded = 1 and (tuition_coverage is not 1)"
    )
    claimed = q("select count(*) n from scholarships where fully_funded = 1")[0]["n"]
    supported = q(
        "select count(*) n from scholarships where fully_funded = 1 and tuition_coverage = 1"
    )[0]["n"]
    print(f"records claiming fully_funded : {claimed}")
    print(f"  of which tuition_coverage=True: {supported}")
    print(f"  VIOLATIONS                   : {len(violation)}")
    for r in violation[:20]:
        print(f"    #{r['id']}: {(r['title'] or '')[:70]}")
    ff_null_tuition = q(
        "select count(*) n from scholarships where fully_funded = 1 and tuition_coverage is null"
    )[0]["n"]
    print(f"claims resting on an unset tuition flag: {ff_null_tuition}")

    rule("2c. PLACE TAXONOMY CONVERGENCE")
    # A country is canonical when the taxonomy can place it, or when it is the
    # explicit "several places" answer. Case is not the test: canonical names are
    # title case, so comparing against lower() flags every correct row.
    known = set(taxonomy.COUNTRY_REGION)
    unplaceable = q(
        "select id,country from scholarships"
        " where country is not null and trim(country) <> ''"
        " and country not in (%s) and country <> '%s'"
        % (",".join("?" * len(known)), taxonomy.MULTIPLE),
        *sorted(known),
    )
    print(f"countries the taxonomy cannot place   : {len(unplaceable)}")
    for r in unplaceable[:15]:
        print(f"    #{r['id']}: {r['country']!r}")
    long_country = q(
        "select id,country from scholarships where length(country) > 60"
    )
    print(f"countries longer than 60 chars       : {len(long_country)}")
    for r in long_country[:10]:
        print(f"    #{r['id']}: {r['country'][:80]!r}")
    unstable_region = q("select id,region from scholarships where length(region) > 40")
    print(f"regions longer than 40 chars         : {len(unstable_region)}")
    for r in unstable_region[:10]:
        print(f"    #{r['id']}: {r['region']!r}")
    aliases_left = q(
        "select count(*) n from scholarships where country in ('USA','UK','US')"
    )[0]["n"]
    print(f"legacy USA/UK spellings remaining    : {aliases_left}")

    rule("3. DATA HYGIENE - schema violations")
    bad_region = q("select id,title,region from scholarships where region is null or trim(region)='' ")
    print(f"region NULL/empty: {len(bad_region)}")
    off = q("select id,region from scholarships where region is not null and region not in (%s)"
            % ",".join("?" * len(REGIONS)), *REGIONS)
    print(f"region not in canonical enum: {len(off)}")
    for r in off[:40]:
        print(f"    #{r['id']}: {(r['region'] or '')[:110]}")
    bad_country = q(
        "select id,country from scholarships where country is not null and trim(country)<>''"
    )
    polluted = [r for r in bad_country if r["country"] not in ISO]
    print(f"\ncountry non-canonical: {len(polluted)} of {len(bad_country)}")
    for r in polluted[:40]:
        print(f"    #{r['id']}: {(r['country'] or '')[:110]}")

    rule("4. LOGO / IMAGE GAPS")
    noimg = q(
        "select id,title,country,official_source,official_source_url,status from scholarships"
        " where image_url is null or trim(image_url)=''"
    )
    print(f"records with NO image: {len(noimg)}")
    hosts = Counter()
    for r in noimg:
        u = r["official_source_url"] or ""
        host = ""
        if "//" in u:
            host = u.split("//", 1)[1].split("/", 1)[0].lower()
        hosts[host or "(no source url)"] += 1
    print(f"distinct hosts needing a logo hunt: {len(hosts)}")
    for h, n in hosts.most_common(60):
        print(f"    {n:>3}  {h}")
    kinds = q(
        "select image_source_type, count(*) n from scholarships where image_url is not null"
        " group by 1 order by n desc"
    )
    print("\nimage_source_type distribution:")
    for r in kinds:
        print(f"    {str(r['image_source_type']):<28} {r['n']}")

    rule("5. DEADLINE GAPS - open/upcoming with no date")
    n = q(
        "select count(*) n from scholarships where status in ('open','upcoming','closing-soon')"
        " and (deadline_date is null or trim(deadline_date)='')"
    )[0]["n"]
    print(f"open/upcoming/closing-soon without deadline_date: {n}")
    prec = q("select deadline_precision, count(*) n from scholarships group by 1 order by n desc")
    print("\ndeadline_precision distribution:")
    for r in prec:
        print(f"    {str(r['deadline_precision']):<18} {r['n']}")

    rule("6. STALE / UNVERIFIED")
    for r in q(
        "select id,title,country,status,last_verified_date,official_source_url from scholarships"
        " where is_verified=0 order by id limit 40"
    ):
        print(f"    #{r['id']:<5} {r['status']:<10} verified={str(r['last_verified_date']):<12} "
              f"{(r['title'] or '')[:60]}")

    rule("7. PREVIOUS WAVE YIELD (shard files on disk)")
    for wave in ("wave1", "wave2", "wave3"):
        files = sorted(glob.glob(os.path.join(ROOT, "research", wave, "out", "*.json")))
        shards_expected = len(
            glob.glob(os.path.join(ROOT, "research", wave, "shards", "*.json"))
        ) - (1 if os.path.exists(
            os.path.join(ROOT, "research", wave, "shards", "MANIFEST.json")) else 0)
        got = new = logos = parse_err = 0
        for f in files:
            d = load_json(f)
            if d is None:
                parse_err += 1
                continue
            got += 1
            if isinstance(d, dict):
                for key in ("records", "shard_results", "items"):
                    for rec in d.get(key) or []:
                        if isinstance(rec, dict) and rec.get("outcome") == "new":
                            new += 1
                            if rec.get("logo_override"):
                                logos += 1
        print(f"  {wave}: expected_shards={shards_expected} files={len(files)} "
              f"parsed={got} parse_err={parse_err} new_records={new} with_logo={logos}")

    rule("8. MERGED WAVE OUTPUTS")
    for p in sorted(glob.glob(os.path.join(ROOT, "research", "wave*", "merged", "*.json"))):
        d = load_json(p)
        size = os.path.getsize(p)
        if isinstance(d, list):
            desc = f"list len={len(d)}"
        elif isinstance(d, dict):
            desc = "keys=" + ",".join(list(d.keys())[:12])
        else:
            desc = "null"
        print(f"  {os.path.relpath(p, ROOT)}  ({size}B)  {desc}")

    rule("9. MAINTENANCE RUNS")
    cols = [r[1] for r in con.execute("PRAGMA table_info(maintenance_runs)")]
    print("columns:", ", ".join(cols))
    order = "id desc"
    if "started_at" in cols:
        order = "started_at desc"
    for r in q(f"select * from maintenance_runs order by {order} limit 12"):
        vals = " | ".join(
            f"{k}={str(r[k])[:40]}" for k in cols
            if k not in ("details", "log", "payload") and r[k] is not None
        )
        print("   ", vals[:300])

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())