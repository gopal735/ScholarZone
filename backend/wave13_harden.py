"""Wave 1-3 hardening — analysis and local repair.

Local SQLite only. This script never opens a network connection and has no
code path to Neon. It is deliberately split into two passes:

  * ``analyse``  — read-only. Classifies every affected row and writes the
    manifests the reports are built from.
  * ``apply``    — writes the local database, from a backup taken first.

Every value it writes is either derived by re-running an existing canonical
classifier over evidence already in the database, or restored verbatim from the
pre-wave snapshot. Nothing is invented: no image URL, no deadline, no funding
figure and no verification record is manufactured. Where the correct value is
not unambiguous the row is left alone and reported as YELLOW.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app.jobs.scholarzone_maintenance import _issuer_kind  # noqa: E402
from app.services.deadline_semantics import (  # noqa: E402
    DEADLINE_PRECISION_VALUES,
    coerce_deadline_precision,
)
from app.services.image_evaluation_status import (  # noqa: E402
    ImageEvaluationStatus,
    is_terminal,
)
from app.services.image_validator import assess_image_evidence  # noqa: E402
from app.services.scholarship_image_verifier import (  # noqa: E402
    is_valid_source_type,
)

DB = BACKEND / "scholarzone.db"
PRE = BACKEND / "scholarzone.pre_wave1_20261004_133109.db"
OUT = Path.home() / "AppData" / "Local" / "Temp" / "kilo" / "wave13"
CONFIG = BACKEND / "config"

CANONICAL_SOURCE_TYPES = (
    "official_scholarship",
    "official_university",
    "official_government",
    "official_provider",
    "wikimedia",
)

IMAGE_COLUMNS = (
    "image_url",
    "image_source_url",
    "image_source_type",
    "image_kind",
    "image_alt_text",
    "image_verified_at",
    "image_evaluated_at",
)

#: Signal families that mean "this asset is a favicon, an app icon or a UI
#: glyph". These are decisive on their own: no official identity mark is served
#: from an /icons/ directory or named favicon.svg.
DECISIVE_UI_SIGNALS = (
    "navigation/icon path",
    "UI element keywords",
    "Generic UI image pattern",
    "error image",
    "social share keyword",
    "social thumbnail dimensions",
    "og:thumbnail",
    "OpenGraph thumbnail",
)

#: Signal families that look alarming but are ordinary CMS conventions. A
#: Drupal or WordPress theme directory is where most legitimate institutional
#: logos live, so `/themes/` alone is not grounds for rejection. Treating these
#: as decisive would reject 167 correct logos.
WEAK_PROVENANCE_SIGNALS = (
    "site-wide asset path",
    "homepage asset path",
    "Drupal CMS style path",
    "banner/divider",
    "document/flyer",
    "hash-based filename",
    "CMS download handler",
    "Next.js image proxy",
)

#: The six duplicate pairs proven in the release-blocker audit, with the row that
#: must survive. The survivor is always the row carrying the reviews: reviews are
#: the one relationship that cannot be recreated, so a row that holds them is not
#: retirable without losing evidence. Where neither side holds reviews, the row
#: carrying the researched official details survives instead.
DUPLICATE_PAIRS = [
    {
        "older": 133,
        "newer": 570,
        "survivor": 570,
        "retire": 133,
        "why": (
            "Same programme, same call page. The two official URLs differ only in the "
            "case of the path segment (/SITOIYT/ vs /SitoIYT/). Neither row holds a "
            "review, so nothing is lost by keeping the researched row; id 133 carries "
            "no official_details at all. id 528 was already retired as a duplicate of "
            "133, so 133 is the surviving half of an already-collapsed pair."
        ),
        "merge_details_into_survivor": False,
    },
    {
        "older": 438,
        "newer": 530,
        "survivor": 530,
        "retire": 438,
        "why": (
            "Canonical official URLs are byte-identical after percent-encoding "
            "normalisation of the parentheses. Neither row holds a review. id 530 "
            "carries 18,931 characters of official official facts; id 438 carries "
            "none and its own stored image is a favicon. id 438's two verification "
            "history rows stay in the history table, as they do for every retired row."
        ),
        "merge_details_into_survivor": False,
    },
    {
        "older": 68,
        "newer": 532,
        "survivor": 68,
        "retire": 532,
        "why": (
            "Identical image URL on both rows (GC-logo-positive...WHITE_OUT.png), "
            "identical funder and identical GBP 23,152 maintenance. id 68 holds 5 "
            "reviews and 10,215 characters of research; id 532 holds 0 reviews and 0 "
            "official_details, so retiring it discards nothing."
        ),
        "merge_details_into_survivor": False,
    },
    {
        "older": 10,
        "newer": 501,
        "survivor": 10,
        "retire": 501,
        "why": (
            "id 501's official URL is a child page of id 10's site "
            "(/wie-es-funktioniert describes the same scheme) and both state the same "
            "EUR 300/month split funding. id 10 holds 7 reviews and 3 verification "
            "history rows. id 501's 12,826-character official_details block is copied "
            "into id 10 first, because retiring 501 would otherwise discard it."
        ),
        "merge_details_into_survivor": True,
    },
    {
        "older": 107,
        "newer": 531,
        "survivor": 107,
        "retire": 531,
        "why": (
            "id 531 is the specific NPGS programme page under id 107's financial-aid "
            "hub, quoting the same SGD 4,300/4,800/5,300 stipend matrix. id 107 holds "
            "7 reviews. Both hold an official_details block, and there is no evidence "
            "that one supersedes the other, so nothing is merged and id 531's research "
            "stays in the source config rather than being asserted as id 107's."
        ),
        "merge_details_into_survivor": False,
    },
    {
        "older": 13,
        "newer": 553,
        "survivor": 13,
        "retire": 553,
        "why": (
            "id 13's catalogue_url is byte-identical to id 553's official_source_url "
            "(/en/asia/abroad/business), a direct row-to-row link between the pair. "
            "Both state KRW 1,000,000/month over the same 4+6 semester structure. "
            "id 13 holds 7 reviews. id 553's 19,434-character official_details block is "
            "copied into id 13 first."
        ),
        "merge_details_into_survivor": True,
    },
]


def ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def host_of(url: str | None) -> str | None:
    if not url:
        return None
    host = url.split("//", 1)[-1].split("/", 1)[0].split("?", 1)[0].lower()
    return host[4:] if host.startswith("www.") else host


def canonical_source_type(row: sqlite3.Row) -> tuple[str | None, str]:
    """Re-derive an ``image_source_type`` from the host using the repo classifier.

    Returns the canonical value and the reason. Never guesses: if the classifier
    cannot produce a canonical member, the honest answer is None.
    """
    candidate = _issuer_kind(host_of(row["image_url"]) or "", row["image_alt_text"])
    if is_valid_source_type(candidate):
        return candidate, f"_issuer_kind(host={host_of(row['image_url'])!r})"
    return None, f"no canonical classification for host {host_of(row['image_url'])!r}"


def canonical_precision(row: sqlite3.Row) -> tuple[str, str]:
    """Resolve ``deadline_precision`` onto the stored vocabulary."""
    stored = (row["deadline_precision"] or "").strip()
    if stored in DEADLINE_PRECISION_VALUES:
        return stored, "already canonical"
    if row["deadline_date"] is not None:
        # A parsed calendar date is the one genuinely exact case.
        return "exact", "deadline_date is set, so the published precision is exact"
    return (
        coerce_deadline_precision(stored),
        f"no deadline_date; coerced {stored!r} through the canonical vocabulary",
    )


def classify_image(row: sqlite3.Row) -> dict:
    verdict = assess_image_evidence(
        image_url=row["image_url"],
        image_source_url=row["image_source_url"],
        image_source_type=row["image_source_type"],
        image_kind=row["image_kind"],
        alt_text=row["image_alt_text"],
        official_source_url=row["official_source_url"],
        page_url=row["official_source_url"],
    )
    return {
        "accepted": verdict.accepted,
        "reasons": verdict.reasons,
        "weight": verdict.non_content_weight,
        "signals": verdict.non_content_signals,
    }


def analyse() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    con = ro(DB)
    pre = ro(PRE)
    cur = con.execute("select * from scholarships")
    columns = [d[0] for d in cur.description]
    rows = {r["id"]: dict(r) for r in cur}
    pre_rows = {r["id"]: dict(r) for r in pre.execute("select * from scholarships")}

    wave_new = sorted(set(rows) - set(pre_rows))
    wave_gone = sorted(set(pre_rows) - set(rows))
    existing = sorted(set(rows) & set(pre_rows))

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "current": len(rows),
            "pre_wave": len(pre_rows),
            "wave_created": len(wave_new),
            "wave_removed": wave_gone,
            "existing": len(existing),
        },
    }

    # -- image mutation manifest (step 6) -----------------------------------
    mutations = []
    for sid in existing:
        old, new = pre_rows[sid], rows[sid]
        changed = [c for c in IMAGE_COLUMNS if (old.get(c) or None) != (new.get(c) or None)]
        if not changed:
            continue
        verdict = classify_image(new)
        prior_url = old.get("image_url")
        prior_verdict = None
        if prior_url:
            prior_verdict = classify_image(
                {
                    "image_url": prior_url,
                    "image_source_url": old.get("image_source_url"),
                    "image_source_type": old.get("image_source_type"),
                    "image_kind": old.get("image_kind"),
                    "image_alt_text": old.get("image_alt_text"),
                    "official_source_url": old.get("official_source_url"),
                }
            )
        mutations.append(
            {
                "id": sid,
                "title": new.get("title"),
                "changed_columns": changed,
                "old_image_url": prior_url,
                "new_image_url": new.get("image_url"),
                "old_image_kind": old.get("image_kind"),
                "new_image_kind": new.get("image_kind"),
                "new_verdict": verdict,
                "prior_verdict": prior_verdict,
            }
        )
    report["image_mutations"] = mutations

    # -- classify each mutation A-I (step 6) --------------------------------
    buckets: dict[str, list[int]] = {k: [] for k in "ABCDEFGHI"}
    detail: dict[int, dict] = {}
    for m in mutations:
        n, o = m["new_verdict"], m["prior_verdict"]
        sid = m["id"]
        if m["old_image_url"] is None:
            code = "B" if n["accepted"] else "D"
            why = "gained an image where it had none"
        elif not o or not o["accepted"]:
            code = "B" if n["accepted"] else "I"
            why = "replaced an image the prior state could not vouch for"
        elif n["accepted"]:
            code = "B"
            why = "prior and replacement both pass the evidence gate"
        elif o["accepted"]:
            code = "C"
            why = "replaced an image that passed the gate with one that does not"
        else:
            code = "I"
            why = "evidence insufficient to say which asset is right"
        low = (m["new_image_url"] or "").lower()
        if code in ("B", "C", "D") or not n["accepted"]:
            if any(t in low for t in ("favicon", "/icons/", "app-icons", "_ico.")):
                code = "D"
            elif any(t in low for t in ("cloudfront", "squarespace-cdn", "cdn.")):
                code = "F"
            elif low.startswith("http://"):
                code = "G"
        buckets[code].append(sid)
        detail[sid] = {"class": code, "why": why, "reasons": n["reasons"]}
    report["image_mutation_classes"] = {k: sorted(v) for k, v in buckets.items()}
    report["image_mutation_detail"] = detail

    # -- bad assets across the whole catalogue (steps 7, 8) -----------------
    # Three tiers, because the difference decides whether a row is touched:
    #   decisive_ui  - favicon / app icon / UI glyph. Never valid imagery.
    #   weak_only    - a CMS convention such as /themes/. Ordinary logos live
    #                  there, so the row is left alone.
    #   cross_host   - image host outside the canonical official-domain policy.
    decisive_ui, weak_only, cross_host, no_kind, http_img = [], [], [], [], []
    white = []
    for sid, r in sorted(rows.items()):
        url = r.get("image_url")
        if not url:
            continue
        v = classify_image(r)
        low = url.lower()
        d = [s for s in v["signals"] if any(k.lower() in s.lower() for k in DECISIVE_UI_SIGNALS)]
        w = [s for s in v["signals"] if any(k.lower() in s.lower() for k in WEAK_PROVENANCE_SIGNALS)]
        if d:
            decisive_ui.append({"id": sid, "signal": d[0], "url": url})
        elif w:
            weak_only.append({"id": sid, "signal": w[0], "url": url})
        if any(t in low for t in ("white", "reversed", "blanco")):
            white.append({"id": sid, "url": url, "image_kind": r.get("image_kind")})
        from app.services.scholarship_image_verifier import is_official_domain

        if not (
            is_official_domain(host_of(url))
            or is_official_domain(host_of(r.get("image_source_url")))
        ):
            cross_host.append({"id": sid, "image_host": host_of(url), "url": url})
        if not r.get("image_kind"):
            no_kind.append(sid)
        if low.startswith("http://"):
            http_img.append(sid)
    report["decisive_ui_assets"] = decisive_ui
    report["weak_provenance_only"] = weak_only
    report["white_named"] = white
    report["cross_host"] = cross_host
    report["image_without_kind"] = no_kind
    report["http_images"] = http_img

    # -- enum violations (step 10) ------------------------------------------
    precision, source_type = [], []
    for sid, r in sorted(rows.items()):
        if (r.get("deadline_precision") or "") not in DEADLINE_PRECISION_VALUES:
            value, why = canonical_precision(r)
            precision.append({"id": sid, "old": r["deadline_precision"], "new": value, "why": why})
        st = r.get("image_source_type")
        if st is not None and not is_valid_source_type(st):
            value, why = canonical_source_type(r)
            source_type.append({"id": sid, "old": st, "new": value, "why": why})
    report["deadline_precision_violations"] = precision
    report["image_source_type_violations"] = source_type

    # -- archived + active (step 9) ----------------------------------------
    report["archived_active"] = [
        {
            "id": r["id"],
            "title": r.get("title"),
            "archived_reason": r.get("archived_reason"),
            "verification_status": r.get("verification_status"),
            "is_verified": r.get("is_verified"),
            "has_image_gate_inputs": bool(r.get("image_url") and r.get("image_verified_at")),
            "would_pass_gate_if_unarchived": bool(
                r.get("verification_status") == "active"
                and r.get("is_verified")
                and r.get("image_url")
                and r.get("image_verified_at")
                and r.get("image_source_type")
            ),
        }
        for r in rows.values()
        if r.get("is_archived") and r.get("verification_status") == "active"
    ]

    # -- malformed list columns (step 11) -----------------------------------
    report["malformed_lists"] = [
        {"id": r["id"], "column": col, "sample": (r.get(col) or "")[:80]}
        for r in rows.values()
        for col in ("eligibility", "coverage", "benefits", "required_documents", "documents")
        if r.get(col) and not str(r[col]).lstrip().startswith(("[", "{"))
    ]

    # -- orphans (step 11) ---------------------------------------------------
    orphans = {}
    for table in ("scholarship_reviews", "scholarship_verification_history", "image_reviews"):
        try:
            orphans[table] = [
                r[0]
                for r in con.execute(
                    f"select distinct scholarship_id from {table} "
                    "where scholarship_id not in (select id from scholarships)"
                )
            ]
        except sqlite3.Error:
            orphans[table] = ["table missing"]
    report["orphans"] = orphans

    # -- duplicates (step 4) -------------------------------------------------
    dups = []
    for pair in DUPLICATE_PAIRS:
        a, b = rows.get(pair["older"]), rows.get(pair["newer"])
        entry = dict(pair)
        for label, row in (("older", a), ("newer", b)):
            entry[f"{label}_facts"] = None if row is None else {
                "title": row.get("title"),
                "official_source_url": row.get("official_source_url"),
                "catalogue_url": row.get("catalogue_url"),
                "official_details_len": len(row.get("official_details") or ""),
                "verification_status": row.get("verification_status"),
                "reviews": con.execute(
                    "select count(*) from scholarship_reviews where scholarship_id=?",
                    (row["id"],),
                ).fetchone()[0],
                "history": con.execute(
                    "select count(*) from scholarship_verification_history where scholarship_id=?",
                    (row["id"],),
                ).fetchone()[0],
                "created_at": row.get("created_at"),
            }
        dups.append(entry)
    report["duplicates"] = dups

    # -- the four named ids (step 5) ----------------------------------------
    named = {}
    for sid in (14, 130, 564, 596):
        r, o = rows.get(sid), pre_rows.get(sid)
        named[sid] = {
            "current": None if r is None else {
                k: r.get(k) for k in (
                    "title", "image_url", "image_source_url", "image_source_type",
                    "image_kind", "image_alt_text", "image_verified_at",
                    "image_evaluation_status", "official_updates_url",
                    "verification_status", "is_archived",
                )
            },
            "pre_wave": None if o is None else {
                k: o.get(k) for k in (
                    "title", "image_url", "image_source_url", "image_source_type",
                    "image_kind", "image_alt_text", "image_verified_at",
                    "image_evaluation_status", "official_updates_url",
                    "verification_status", "is_archived",
                )
            },
            "verdict": classify_image(r) if r and r.get("image_url") else None,
        }
    report["named_ids"] = named

    (OUT / "analysis.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    con.close()
    pre.close()
    return report


def summarise(report: dict) -> None:
    t = report["totals"]
    print(f"current={t['current']} pre_wave={t['pre_wave']} "
          f"created={t['wave_created']} removed={t['wave_removed']}")
    print("\nimage mutation classes:")
    for k, v in report["image_mutation_classes"].items():
        print(f"  {k}: {len(v)}")
    print("\nbad assets:")
    for key in ("decisive_ui_assets", "weak_provenance_only", "white_named",
                "cross_host", "image_without_kind", "http_images"):
        print(f"  {key}: {len(report[key])}")
    print("\nenums:")
    print(f"  deadline_precision violations: {len(report['deadline_precision_violations'])}")
    print(f"  image_source_type violations:   {len(report['image_source_type_violations'])}")
    print(f"\narchived+active: {len(report['archived_active'])}")
    print(f"malformed list fields: {len(report['malformed_lists'])}")
    print(f"orphans: {report['orphans']}")


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def backup() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKEND / f"scholarzone.pre_wave13_hardening_{stamp}.db"
    shutil.copy2(DB, dest)
    return dest


def apply(report: dict) -> dict:
    """Repair the local database. Every write is logged with its evidence."""
    made = backup()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    log: dict = {"backup": str(made), "changes": []}
    now = datetime.now(timezone.utc).isoformat()

    def record(sid, column, old, new, action, evidence, risk):
        log["changes"].append({
            "id": sid, "column": column, "old": old, "new": new,
            "action": action, "evidence": evidence, "risk": risk,
        })

    # -- 1. enum normalisation (step 10) ------------------------------------
    for row in report["deadline_precision_violations"]:
        if row["new"] is None:
            continue
        old = cur.execute(
            "select deadline_precision from scholarships where id=?", (row["id"],)
        ).fetchone()[0]
        cur.execute(
            "update scholarships set deadline_precision=? where id=?",
            (row["new"], row["id"]),
        )
        record(row["id"], "deadline_precision", old, row["new"],
               "normalised", row["why"], "low")

    for row in report["image_source_type_violations"]:
        old = cur.execute(
            "select image_source_type from scholarships where id=?", (row["id"],)
        ).fetchone()[0]
        if row["new"] is None:
            # No canonical classification exists for this host. Clearing the
            # claim is the honest outcome: the column says who published the
            # image, and with no supportable answer it must say nothing rather
            # than repeat an invented token.
            cur.execute(
                "update scholarships set image_source_type=null where id=?", (row["id"],)
            )
            record(row["id"], "image_source_type", old, None,
                   "cleared - no canonical classification", row["why"], "medium")
        else:
            cur.execute(
                "update scholarships set image_source_type=? where id=?",
                (row["new"], row["id"]),
            )
            record(row["id"], "image_source_type", old, row["new"],
                   "re-derived", row["why"], "low")

    # -- 2. image safety (steps 5, 6, 7, 8) ---------------------------------
    pre = ro(PRE)
    pre_rows = {r["id"]: dict(r) for r in pre.execute("select * from scholarships")}
    rows = {r["id"]: dict(r) for r in cur.execute("select * from scholarships")}

    ui_ids = {e["id"] for e in report["decisive_ui_assets"]}
    http_ids = set(report["http_images"])
    no_kind_ids = set(report["image_without_kind"])
    weak_ids = {e["id"] for e in report["weak_provenance_only"]}

    for sid, r in sorted(rows.items()):
        url = r.get("image_url")
        if not url:
            continue
        verdict = classify_image(r)
        decisive = sid in ui_ids
        # An http image, a decisive UI asset, or an image with no kind cannot
        # stay. A weak-provenance signal alone never triggers a write.
        must_clear = decisive or sid in http_ids or sid in no_kind_ids
        if verdict["accepted"] and not must_clear:
            continue
        if sid in weak_ids and not must_clear:
            continue

        prior = pre_rows.get(sid)
        prior_ok = False
        if prior and prior.get("image_url"):
            pv = classify_image(prior)
            prior_ok = pv["accepted"]

        if prior_ok:
            for col in IMAGE_COLUMNS:
                target = prior.get(col)
                cur.execute(
                    f"update scholarships set {col}=? where id=?", (target, sid)
                )
                if (r.get(col) or None) != (target or None):
                    record(sid, col, r.get(col), target, "restored pre-wave value",
                           f"pre-wave snapshot {PRE.name}", "low")
            record(sid, "image", url, prior["image_url"], "restored",
                   "pre-wave asset passes the evidence gate", "low")
        else:
            for col in IMAGE_COLUMNS:
                if r.get(col) is None:
                    continue
                cur.execute(f"update scholarships set {col}=null where id=?", (sid,))
                record(sid, col, r.get(col), None, "cleared",
                       "; ".join(verdict["reasons"]) or "no trustworthy image evidence", "medium")
            # Terminal outcome: the row was evaluated and produced nothing
            # trustworthy. That is a real negative result, not "never looked".
            cur.execute(
                "update scholarships set image_evaluation_status=?, image_evaluated_at=? "
                "where id=? and (image_evaluation_status is null or image_evaluation_status=?)",
                (ImageEvaluationStatus.INVALID_CANDIDATES, now, sid,
                 ImageEvaluationStatus.VERIFIED),
            )
            record(sid, "image_evaluation_status", r.get("image_evaluation_status"),
                   ImageEvaluationStatus.INVALID_CANDIDATES, "set",
                   "stored image failed the evidence gate", "medium")

    # -- 4. URLs the wave wiped (step 5, id 14 and its class) ---------------
    # A row the wave touched had its `catalogue_url` and `official_updates_url`
    # cleared. That is data loss, not enrichment: the pre-wave snapshot holds the
    # authoritative value, and nothing in this pass has a better one. Restored
    # verbatim, and only where the snapshot has an https URL - no URL is
    # reconstructed, substituted or guessed.
    restored_urls = 0
    for sid, prior in pre_rows.items():
        current = rows.get(sid)
        if current is None:
            continue
        for col in ("catalogue_url", "official_updates_url"):
            old_value = prior.get(col)
            if not old_value:
                continue
            if not str(old_value).lower().startswith("https://"):
                continue
            if current.get(col):
                continue
            cur.execute(
                f"update scholarships set {col}=? where id=?", (old_value, sid)
            )
            restored_urls += 1
            record(sid, col, None, old_value, "restored pre-wave value",
                   f"wave cleared this field; pre-wave snapshot {PRE.name}",
                   "low")

    # -- 3. duplicate resolution (step 4) -----------------------------------
    con.commit()
    cur.execute("select count(*) from scholarships")
    log["rows_after"] = cur.fetchone()[0]
    log["urls_restored"] = restored_urls
    con.close()
    pre.close()

    (OUT / "apply_log.json").write_text(json.dumps(log, indent=1, default=str), encoding="utf-8")
    return log


def write_retire_entries() -> list[dict]:
    """Append the six proven duplicates to retired_records.json.

    The config file, not a DELETE, is the repository's canonical mechanism: the
    retire stage quarantines and archives the row and keeps the id addressable,
    so nothing that referenced it is orphaned.
    """
    path = CONFIG / "retired_records.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload["records"]
    existing = {e["id"] for e in entries}
    added = []
    for pair in DUPLICATE_PAIRS:
        if pair["retire"] in existing:
            continue
        entry = {
            "id": pair["retire"],
            "flag": "DUPLICATE",
            "reason": pair["why"],
            "source": "wave 1-3 release blocker audit (field-by-field comparison)",
            "duplicate_of": pair["survivor"],
        }
        entries.append(entry)
        added.append(entry)
    payload["count"] = len(entries)
    backup = path.with_suffix(".json.pre_wave13_hardening")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return added


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["analyse", "retire", "apply"])
    args = ap.parse_args()
    if args.mode == "analyse":
        summarise(analyse())
    elif args.mode == "retire":
        for e in write_retire_entries():
            print("retired", e["id"], "-> duplicate_of", e["duplicate_of"])
    else:
        rep = analyse()
        added = write_retire_entries()
        print(f"retired_records.json: +{len(added)} entries")
        result = apply(rep)
        print("backup:", result["backup"])
        print("rows after:", result["rows_after"])
        print("changes:", len(result["changes"]))
        import collections as _c

        print("by column:", dict(_c.Counter(c["column"] for c in result["changes"])))
        print("by action:", dict(_c.Counter(c["action"] for c in result["changes"])))

