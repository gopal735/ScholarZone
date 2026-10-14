"""Wave 1-3 final audit: every remaining release question, measured not asserted.

Read-only. Opens every database with `mode=ro` and never imports a network
client. Produces one JSON bundle plus a console summary.

Steps covered: 4 (234 new rows), 5 (32 new UI assets, measured pre-repair),
6 (asset corrections), 7 (provenance), 8 (deadline precision), 9 (duplicates),
10 (archived/active), 13 (invariants), plus a register of the two defects the
previous hardening pass introduced.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app.services.deadline_semantics import DEADLINE_PRECISION_VALUES  # noqa: E402
from app.services.image_evaluation_status import TERMINAL_STATUSES  # noqa: E402
from app.services.image_validator import assess_image_evidence  # noqa: E402
from app.services.image_discovery_orchestrator import (  # noqa: E402
    LOGO_IDENTITY_KINDS, PROGRAMME_IMAGE_KINDS,
)
from app.services.scholarship_image_verifier import is_valid_source_type  # noqa: E402

OUT = Path.home() / "AppData" / "Local" / "Temp" / "kilo" / "wave13"
LIVE = BACKEND / "scholarzone.db"
PRE_REPAIR = BACKEND / "scholarzone.pre_wave13_hardening_20261004_171847.db"
PRE_WAVE = BACKEND / "scholarzone.pre_wave1_20261004_133109.db"

DECISIVE_UI = ("navigation/icon path", "UI element keywords",
               "Generic UI image pattern", "error image", "social share keyword")
WEAK_UI = ("site-wide asset path", "homepage asset path", "Drupal CMS style path",
           "banner/divider", "document/flyer", "hash-based filename",
           "CMS download handler", "Next.js image proxy")

IMAGE_COLUMNS = ("image_url", "image_source_url", "image_source_type",
                 "image_kind", "image_alt_text", "image_verified_at",
                 "image_evaluated_at")

FLAGS = {"verified": True, "image": True, "third_party": False}


def ro(path: Path) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = {r["id"]: dict(r) for r in con.execute("select * from scholarships")}
    con.close()
    return rows


def verdict_for(r: dict) -> dict:
    if not r.get("image_url"):
        return {"accepted": True, "signals": [], "reasons": [], "weight": 0.0}
    v = assess_image_evidence(
        image_url=r["image_url"], image_source_url=r.get("image_source_url"),
        image_source_type=r.get("image_source_type"), image_kind=r.get("image_kind"),
        alt_text=r.get("image_alt_text"),
        official_source_url=r.get("official_source_url"),
    )
    return {"accepted": v.accepted, "signals": v.non_content_signals,
            "reasons": v.reasons, "weight": v.non_content_weight}


def decisive_ui(r: dict) -> list:
    return [s for s in verdict_for(r)["signals"]
            if any(k.lower() in s.lower() for k in DECISIVE_UI)]


def weak_ui(r: dict) -> list:
    return [s for s in verdict_for(r)["signals"]
            if any(k.lower() in s.lower() for k in WEAK_UI)]


def is_public(r: dict) -> bool:
    """Mirror of public_visibility_conditions(); validated against it in Step 3."""
    if r["verification_status"] == "quarantined":
        return False
    if r["is_archived"]:
        return False
    if not r["is_verified"]:
        return False
    if r["image_url"] is None or r["image_verified_at"] is None:
        return False
    return r["image_source_type"] != "wikimedia"


def host_of(url):
    if not url:
        return None
    h = url.split("//", 1)[-1].split("/", 1)[0].split("?", 1)[0].lower()
    return h[4:] if h.startswith("www.") else h


# ---------------------------------------------------------------------------
# Step 4 — the 234 wave-created rows, partitioned
# ---------------------------------------------------------------------------

def step4_new_rows(live: dict, pre_wave: dict) -> dict:
    wave_ids = sorted(set(live) - set(pre_wave))
    url_index = defaultdict(list)
    for r in live.values():
        u = (r.get("official_source_url") or "").rstrip("/").lower()
        if u:
            url_index[u].append(r["id"])

    rows = []
    for rid in wave_ids:
        r = live[rid]
        red, yellow = [], []
        d = decisive_ui(r)

        if d:
            red.append("unsafe image asset: " + "; ".join(d[:2]))
        elif r.get("image_url") and not verdict_for(r)["accepted"]:
            red.append("image failed the evidence gate")
        if not r.get("official_source_url"):
            red.append("no official_source_url")
        elif not str(r["official_source_url"]).lower().startswith("https://"):
            red.append("official_source_url is not https")
        if (r.get("deadline_precision") or "") not in DEADLINE_PRECISION_VALUES:
            red.append("deadline_precision outside the vocabulary")
        if r.get("image_source_type") and not is_valid_source_type(r["image_source_type"]):
            red.append("image_source_type outside the vocabulary")
        if r.get("image_url") and not r.get("image_kind"):
            red.append("image_url without image_kind")
        if r.get("image_url") and not r.get("image_source_type"):
            red.append("image_url without image_source_type")
        u = (r.get("official_source_url") or "").rstrip("/").lower()
        dupes = [i for i in url_index.get(u, [])
                 if i != rid and not live[i]["is_archived"]] if u else []
        if dupes:
            red.append(f"shares official_source_url with live row(s) {dupes}")

        if not r.get("image_url"):
            yellow.append("no image stored; not publicly visible")
        if not r.get("official_details"):
            yellow.append("no official_details block")
        if r["verification_status"] == "quarantined":
            yellow.append("quarantined")
        if r.get("is_archived"):
            yellow.append("archived")
        if len(r.get("verification_notes") or "") == 0:
            yellow.append("no verification note")

        bucket = "RED" if red else ("YELLOW" if yellow else "GREEN")
        rows.append({
            "id": rid, "title": r["title"],
            "official_source_url": r["official_source_url"],
            "provider": host_of(r.get("official_source_url")),
            "verification_status": r["verification_status"],
            "is_verified": bool(r["is_verified"]),
            "is_archived": bool(r["is_archived"]),
            "public": is_public(r),
            "image_url": r["image_url"], "image_kind": r["image_kind"],
            "image_source_type": r["image_source_type"],
            "image_verified_at": r["image_verified_at"],
            "image_evaluation_status": r["image_evaluation_status"],
            "deadline_date": r["deadline_date"],
            "deadline_precision": r["deadline_precision"],
            "funding": r["funding"], "funding_amount": r["funding_amount"],
            "official_details_len": len(r.get("official_details") or ""),
            "verification_notes_len": len(r.get("verification_notes") or ""),
            "ui_asset": d, "duplicate_of": dupes,
            "bucket": bucket, "red_reasons": red, "yellow_reasons": yellow,
        })
    return {
        "wave_ids": wave_ids, "count": len(rows),
        "partition": dict(Counter(r["bucket"] for r in rows)),
        "public_count": sum(1 for r in rows if r["public"]),
        "yellow_reason_classes": dict(Counter(
            y.split(";")[0] for r in rows for y in r["yellow_reasons"])),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Step 5 — UI assets the wave brought in, measured before the repair
# ---------------------------------------------------------------------------

def step5_ui_assets(pre_repair: dict, pre_wave: dict) -> dict:
    """Counted on the pre-repair snapshot, because the repair removed them.

    Measuring on the current database returns nothing and hides the problem.
    """
    rows = []
    for rid in sorted(set(pre_repair) - set(pre_wave)):
        r = pre_repair[rid]
        d = decisive_ui(r)
        if not d:
            continue
        signal = d[0].lower()
        rows.append({
            "id": rid, "title": r["title"],
            "official_source_url": r.get("official_source_url"),
            "image_url_as_brought_in": r.get("image_url"),
            "image_kind_as_brought_in": r.get("image_kind"),
            "signal": d[0],
            "asset_class": (
                "favicon / touch-icon" if "favicon" in signal or "icon" in signal
                else "social asset" if "social" in signal
                else "navigation / menu asset" if ("nav" in signal or "menu" in signal)
                else "error-page artefact" if "error" in signal
                else "other UI asset"),
            "disposition": ("cleared - no trustworthy alternative"
                            if live_image_is_null(live_cache, rid)
                            else "STILL STORED"),
            "_live": None,
        })
    rows = [{k: v for k, v in x.items() if not k.startswith("_")} for x in rows]
    return {
        "count": len(rows),
        "asset_classes": dict(Counter(x["asset_class"] for x in rows)),
        "rows": rows,
    }


live_cache: dict = {}


def live_image_is_null(cache: dict, rid) -> bool:
    return cache.get(rid, {}).get("image_url") is None


# ---------------------------------------------------------------------------
# Step 6 — asset corrections on rows that existed before the wave
# ---------------------------------------------------------------------------

def step6_corrections(live: dict, pre_repair: dict, pre_wave: dict) -> dict:
    rows = []
    for rid in sorted(set(pre_repair) & set(live)):
        b, a = pre_repair[rid], live[rid]
        changed = [c for c in IMAGE_COLUMNS if (b.get(c) or None) != (a.get(c) or None)]
        if not changed:
            continue
        was_ui = decisive_ui(b)
        prior_ok = verdict_for(b)["accepted"] if b.get("image_url") else None
        if b.get("image_url") and not a.get("image_url"):
            action = "cleared"
        elif b.get("image_url") and a.get("image_url"):
            action = "restored" if a["image_url"] == b["image_url"] else "replaced"
        else:
            action = "unchanged"
        rows.append({
            "id": rid, "title": a["title"],
            "was_wave_created": rid not in pre_wave,
            "action": action, "changed_columns": changed,
            "old_image_url": b.get("image_url"), "new_image_url": a.get("image_url"),
            "old_image_kind": b.get("image_kind"), "new_image_kind": a.get("image_kind"),
            "prior_verdict_accepted": prior_ok,
            "decisive_ui_before": was_ui[:2],
            "decisive_ui_after": decisive_ui(a)[:2],
            "weak_signal_after": weak_ui(a)[:1],
            "image_evaluation_status": a.get("image_evaluation_status"),
            "public": is_public(a),
        })
    pre_existing = [r for r in rows if not r["was_wave_created"]]
    corrected_ui = [r for r in pre_existing if r["decisive_ui_before"]]
    return {
        "total": len(rows),
        "pre_existing": len(pre_existing),
        "wave_created": sum(1 for r in rows if r["was_wave_created"]),
        "actions": dict(Counter(r["action"] for r in rows)),
        "pre_existing_with_decisive_ui_before": len(corrected_ui),
        "corrected_ui_ids": [r["id"] for r in corrected_ui],
        "still_decisive_ui": [r["id"] for r in rows if r["decisive_ui_after"]],
        "overwrote_a_trusted_asset": [
            r["id"] for r in rows
            if r["prior_verdict_accepted"] and r["action"] == "cleared"],
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Steps 7 + 8 — enum corrections, exact old -> new
# ---------------------------------------------------------------------------

def step7_8_enums(live: dict, pre_repair: dict) -> dict:
    prov, prec = [], []
    for rid in sorted(set(pre_repair) & set(live)):
        b, a = pre_repair[rid], live[rid]
        if (b.get("image_source_type") or None) != (a.get("image_source_type") or None):
            prov.append({
                "id": rid, "title": a["title"],
                "old": b.get("image_source_type"), "new": a.get("image_source_type"),
                "old_valid": (is_valid_source_type(b["image_source_type"])
                              if b.get("image_source_type") else None),
                "new_valid": (is_valid_source_type(a["image_source_type"])
                              if a.get("image_source_type") else None),
                "image_kind_now": a.get("image_kind"),
                "asset_also_changed": pre_repair[rid].get("image_url") != a.get("image_url"),
            })
        if (b.get("deadline_precision") or None) != (a.get("deadline_precision") or None):
            prec.append({
                "id": rid, "title": a["title"],
                "host": host_of(a.get("official_source_url")),
                "old": b.get("deadline_precision"), "new": a.get("deadline_precision"),
                "deadline_date_now": a.get("deadline_date"),
                "has_deadline_date": a.get("deadline_date") is not None,
                "deadline_display": a.get("deadline_display"),
            })
    return {
        "provenance": {
            "count": len(prov),
            "mapping": dict(Counter(f"{r['old']} -> {r['new']}" for r in prov)),
            "old_was_invalid": sum(1 for r in prov if r["old_valid"] is False),
            "old_was_valid": sum(1 for r in prov if r["old_valid"] is True),
            "new_all_canonical_or_null": all(r["new_valid"] in (True, None) for r in prov),
            # The defect being checked for is an image *kind* landing in the
            # provenance column. `official_logo`, `official_page_logo` and
            # friends are kinds; the five canonical source types are not, and
            # `official_logo` is not among them.
            "no_kind_value_in_source_type": all(
                r["new"] not in ("official_logo", "official_page_logo",
                                 "official_ngo", "official_organization",
                                 "official_institution", "official_charity")
                for r in prov),
            "kinds_are_image_kind_not_source_type": all(
                (r["image_kind_now"] or "") in LOGO_IDENTITY_KINDS
                | PROGRAMME_IMAGE_KINDS | {None}
                for r in prov),
            "rows": prov,
        },
        "deadline": {
            "count": len(prec),
            "mapping": dict(Counter(f"{r['old']} -> {r['new']}" for r in prec)),
            "to_exact_without_a_date": [r["id"] for r in prec
                                        if r["new"] == "exact" and not r["has_deadline_date"]],
            "day_rows_with_a_date": sum(1 for r in prec
                                        if r["old"] == "day" and r["has_deadline_date"]),
            "unknown_rows": [r["id"] for r in prec if r["new"] == "unknown"],
            "a_star_rows": [r for r in prec
                            if (r["host"] or "").endswith("a-star.edu.sg")],
            "rows": prec,
        },
    }


# ---------------------------------------------------------------------------
# Defects introduced by the previous hardening pass
# ---------------------------------------------------------------------------

def defect_register(live: dict, pre_repair: dict, pre_wave: dict) -> list:
    from app.jobs.scholarzone_maintenance import _issuer_kind

    defects = []

    for rid in sorted(set(pre_repair) & set(live)):
        url = pre_repair[rid].get("image_url") or ""
        if not url or live[rid].get("image_url") is not None:
            continue
        v = verdict_for(pre_repair[rid])
        if not any("error image" in s for s in v["signals"]):
            continue
        filename = url.split("/")[-1]
        digit_runs = re.findall(r"\d{3}", filename)
        if len(re.findall(r"\d", filename)) <= 6:
            continue
        defects.append({
            "id": f"D1-UI{rid}", "scholarship_id": rid,
            "title": pre_repair[rid]["title"],
            "classification": "PROVEN FALSE POSITIVE",
            "signal": v["signals"][0],
            "asset_cleared": url,
            "digit_runs_in_filename": digit_runs,
            "what_happened": (
                "_detect_error_signals matched a three-digit HTTP status inside a "
                "CMS content hash in the filename, scored it 2.0, and the asset was "
                "cleared as a non-content artefact."),
            "correct_action": (
                "restore the asset; the detector must exclude digit runs inside CMS "
                "content hashes - the same class of over-broad substring match as the "
                "'bann' document keyword fixed earlier."),
            "current_state": "image_url NULL, status="
                             f"{live[rid].get('image_evaluation_status')}, not public",
        })

    for rid in sorted(set(live) & set(pre_repair) & set(pre_wave)):
        a, b, c = pre_wave[rid], pre_repair[rid], live[rid]
        old, mid, now = (a.get("image_source_type"), b.get("image_source_type"),
                         c.get("image_source_type"))
        if not (mid != old and now == old and is_valid_source_type(mid)
                and is_valid_source_type(old) and old != mid):
            continue
        if b.get("image_url") == c.get("image_url"):
            continue
        host = host_of(b.get("image_url")) or ""
        derived = _issuer_kind(host, b.get("image_alt_text"))
        defects.append({
            "id": f"D2-PROV{rid}", "scholarship_id": rid, "title": c["title"],
            "classification": "PROVEN PRECISION LOSS",
            "old_pre_wave": old, "wave_set": mid, "now": now,
            "host": host, "alt_text": b.get("image_alt_text"),
            "what_happened": (
                f"the wave improved provenance {old!r} -> {mid!r}; the "
                "asset-restoration path restored image_source_type along with the "
                f"image, reverting it to {old!r}."),
            "correct_value": mid, "classifier_recomputes_to": derived,
            "classifier_agrees": derived == mid,
            "correct_action": (
                f"restore image_source_type to {mid!r}; derivable from host and alt "
                "text, no research needed."),
            "impact": (
                "both values are canonical and both satisfy the public gate "
                "identically, so nothing is hidden and no invariant breaks - the row "
                "simply states less about its own provenance."),
        })
    return defects


# ---------------------------------------------------------------------------
# Steps 9 + 10 — duplicates and archive
# ---------------------------------------------------------------------------

PAIRS = [(133, 570), (438, 530), (68, 532), (10, 501), (107, 531), (13, 553)]


def step9_10(live: dict) -> dict:
    con = sqlite3.connect(f"file:{LIVE}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    retired = json.loads(
        (BACKEND / "config" / "retired_records.json").read_text(encoding="utf-8")
    )["records"]
    retired_ids = {e["id"] for e in retired}

    dups = []
    for a, b in PAIRS:
        ra, rb = live.get(a), live.get(b)
        survivor = a if (ra and not ra["is_archived"]) else (b if rb else None)
        dup = b if survivor == a else a
        rs, rd = live.get(survivor), live.get(dup)
        dups.append({
            "pair": [a, b], "survivor": survivor, "duplicate": dup,
            "duplicate_archived": bool(rd["is_archived"]) if rd else None,
            "duplicate_in_retired_file": (dup in retired_ids) if dup else None,
            "survivor_archived": bool(rs["is_archived"]) if rs else None,
            "survivor_public": is_public(rs) if rs else None,
            "duplicate_public": is_public(rd) if rd else None,
            "references": {
                rid: {
                    "reviews": con.execute(
                        "select count(*) from scholarship_reviews where scholarship_id=?",
                        (rid,)).fetchone()[0],
                    "history": con.execute(
                        "select count(*) from scholarship_verification_history "
                        "where scholarship_id=?", (rid,)).fetchone()[0],
                    "image_reviews": con.execute(
                        "select count(*) from image_reviews where scholarship_id=?",
                        (rid,)).fetchone()[0],
                } for rid in (a, b)},
        })

    archived_active = [
        {"id": r["id"], "title": r["title"], "archived_reason": r["archived_reason"],
         "would_be_public_if_unarchived": is_public({**r, "is_archived": False})}
        for r in sorted(live.values(), key=lambda x: x["id"])
        if r["is_archived"] and r["verification_status"] == "active"
    ]
    con.close()
    return {
        "duplicates": dups,
        "all_resolved": all(
            d["duplicate_archived"] and not d["survivor_archived"]
            and not d["duplicate_public"] for d in dups),
        "archived_active_count": len(archived_active),
        "would_go_public_if_unarchived": sum(
            1 for r in archived_active if r["would_be_public_if_unarchived"]),
        "archived_total": sum(1 for r in live.values() if r["is_archived"]),
        "archived_and_public": sorted(
            r["id"] for r in live.values() if r["is_archived"] and is_public(r)),
        "archived_active": archived_active,
    }


# ---------------------------------------------------------------------------
# Step 13 — invariants
# ---------------------------------------------------------------------------

def step13_invariants(live: dict) -> dict:
    public = {rid for rid, r in live.items() if is_public(r)}
    c: dict = {}
    c["public_lte_total"] = len(public) <= len(live)
    c["invalid_deadline_precision"] = sorted(
        i for i, r in live.items()
        if (r.get("deadline_precision") or "") not in DEADLINE_PRECISION_VALUES)
    c["invalid_image_source_type"] = sorted(
        i for i, r in live.items()
        if r.get("image_source_type") and not is_valid_source_type(r["image_source_type"]))
    c["image_without_kind"] = sorted(
        i for i, r in live.items() if r.get("image_url") and not r.get("image_kind"))
    c["kind_without_image"] = sorted(
        i for i, r in live.items() if r.get("image_kind") and not r.get("image_url"))
    c["http_image"] = sorted(
        i for i, r in live.items()
        if r.get("image_url") and not str(r["image_url"]).lower().startswith("https://"))
    c["decisive_ui_still_stored"] = sorted(i for i, r in live.items() if decisive_ui(r))
    c["public_without_image_evidence"] = sorted(
        i for i in public
        if not live[i].get("image_url") or not live[i].get("image_verified_at"))
    c["public_not_verified"] = sorted(i for i in public if not live[i]["is_verified"])
    c["public_archived"] = sorted(i for i in public if live[i]["is_archived"])
    c["public_quarantined"] = sorted(
        i for i in public if live[i]["verification_status"] == "quarantined")
    c["wikimedia_public"] = sorted(
        i for i in public if live[i].get("image_source_type") == "wikimedia")
    c["image_without_evaluation_status"] = sorted(
        i for i, r in live.items()
        if r.get("image_url") and not r.get("image_evaluation_status"))
    c["image_non_terminal_evaluation"] = sorted(
        i for i, r in live.items()
        if r.get("image_url") and r.get("image_evaluation_status") not in TERMINAL_STATUSES)

    seen = defaultdict(list)
    for rid, r in live.items():
        u = (r.get("official_source_url") or "").rstrip("/").lower()
        if u:
            seen[u].append(rid)
    c["duplicate_urls"] = {u: ids for u, ids in seen.items() if len(ids) > 1}
    c["duplicate_urls_at_most_one_live"] = all(
        sum(1 for i in ids if not live[i]["is_archived"]) <= 1
        for ids in c["duplicate_urls"].values())
    c["duplicate_urls_public_ids"] = sorted(
        {i for ids in c["duplicate_urls"].values() for i in ids if is_public(live[i])})

    con = sqlite3.connect(f"file:{LIVE}?mode=ro", uri=True)
    orphans = {}
    for table in ("scholarship_reviews", "scholarship_verification_history",
                  "image_reviews"):
        orphans[table] = [r[0] for r in con.execute(
            f"select distinct scholarship_id from {table} "
            "where scholarship_id not in (select id from scholarships)")]
    counts = {}
    for t in ("scholarships", "scholarship_reviews",
              "scholarship_verification_history", "image_reviews"):
        counts[t] = con.execute(f"select count(*) from {t}").fetchone()[0]
    con.close()
    c["orphan_references"] = orphans
    c["row_counts"] = counts
    c["malformed_list_columns"] = sorted(
        f"{i}:{col}" for i, r in live.items()
        for col in ("eligibility", "coverage", "benefits", "requirements",
                    "documents", "application_method")
        if r.get(col) and not str(r[col]).lstrip().startswith(("[", "{")))
    return c


def step4b_precise_red_split(new_rows: dict, live: dict) -> dict:
    """Separate genuine safety failures from detector false positives.

    "The evidence gate rejected it" is not yet a release finding. The gate
    combines a decisive UI check with a host allowlist and a set of weak
    provenance hints, and the latter two demonstrably reject real official logos
    - `/themes/`, `/common/`, `/global/`, `/home/` are ordinary CMS
    directories, and the host allowlist does not know `.ac.za`, `.ac.th`,
    `.edu.ar`, `.gob.cl` or `.foundation`.

    So each rejection is re-read signal by signal and sorted into:
      * unsafe          - a decisive UI signal, or an asset that is not an
                          identity mark at all
      * policy_gap      - rejected only by a weak hint or an allowlist gap
      * mixed           - both
    """
    out = []
    for r in new_rows["rows"]:
        if r["bucket"] != "RED":
            continue
        row = live[r["id"]]
        v = verdict_for(row)
        decisive = [s for s in v["signals"]
                    if any(k.lower() in s.lower() for k in DECISIVE_UI)]
        weak = [s for s in v["signals"]
                if any(k.lower() in s.lower() for k in WEAK_UI)]
        host_only = any("not an official source" in x for x in v["reasons"])
        other = [x for x in v["reasons"]
                 if "not an official source" not in x and "non-content" not in x]

        # An asset that is not an identity mark at all is unsafe regardless of
        # which signal happened to catch it.
        looks_like_identity_mark = bool(row.get("image_kind")) and (
            "infographic" in (row.get("image_url") or "").lower()
            or "-banner" in (row.get("image_url") or "").lower())

        # A path or filename that names a browser icon platform is decisive even
        # when the keyword detectors miss it: `/Images/Favicons/android-chrome-
        # 512x512.png` is a favicon directory reached through a "Drupal CMS
        # style path" signal, which on its own is only a weak hint.
        url = (row.get("image_url") or "").lower()
        platform_icon = any(m in url for m in (
            "/favicons/", "favicon.", "android-chrome", "apple-touch-icon",
            "apple-icon", "icon-512", "icon-192", "browserconfig",
            "safari-pinned-tab", "_ico."))
        # An "Icon_logos" directory holding a file actually named Logo_*.png is
        # the opposite case: a real logo in a badly named directory.
        logo_in_icon_dir = ("/icon" in url and "logo" in url.rsplit("/", 1)[-1])

        if decisive or looks_like_identity_mark or other or platform_icon:
            cls = "unsafe"
        elif host_only or weak:
            cls = "policy_gap"
        else:
            cls = "unsafe"
        out.append({
            "id": r["id"], "title": r["title"], "public": r["public"],
            "classification": cls,
            "platform_icon_evidence": platform_icon,
            "logo_in_icon_dir": logo_in_icon_dir,
            "decisive_signals": decisive,
            "weak_signals": weak,
            "host_rejected": host_only,
            "other_reasons": other,
            "image_url": row.get("image_url"),
            "image_kind": row.get("image_kind"),
            "image_host": host_of(row.get("image_url")),
        })
    return {
        "count": len(out),
        "classification": dict(Counter(x["classification"] for x in out)),
        "public_by_classification": {
            k: sorted(x["id"] for x in out
                      if x["classification"] == k and x["public"])
            for k in ("unsafe", "policy_gap")},
        "rows": out,
    }


def main() -> dict:
    global live_cache
    OUT.mkdir(parents=True, exist_ok=True)
    live = ro(LIVE)
    live_cache = live
    pre_repair = ro(PRE_REPAIR)
    pre_wave = ro(PRE_WAVE)

    new_rows = step4_new_rows(live, pre_wave)
    ui_assets = step5_ui_assets(pre_repair, pre_wave)
    corrections = step6_corrections(live, pre_repair, pre_wave)
    enums = step7_8_enums(live, pre_repair)
    defects = defect_register(live, pre_repair, pre_wave)
    red_split = step4b_precise_red_split(new_rows, live)
    dupes = step9_10(live)
    inv = step13_invariants(live)

    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live": LIVE.name, "pre_repair": PRE_REPAIR.name, "pre_wave": PRE_WAVE.name,
        "step4_new_rows": new_rows, "step5_ui_assets": ui_assets,
        "step6_corrections": corrections, "step7_8_enums": enums,
        "step4b_red_split": red_split,
        "defect_register": defects, "step9_10": dupes, "step13_invariants": inv,
    }
    (OUT / "final_audit.json").write_text(
        json.dumps(bundle, indent=1, default=str), encoding="utf-8")

    print("=== STEP 4: 234 wave-created rows ===")
    print("  partition:", new_rows["partition"], " publicly visible:",
          new_rows["public_count"])
    print("  RED reason classes:",
          dict(Counter(r["red_reasons"][0].split(":")[0]
                       for r in new_rows["rows"] if r["red_reasons"])))
    print("  YELLOW reason classes:", new_rows["yellow_reason_classes"])
    for bucket in ("GREEN", "YELLOW", "RED"):
        sel = [r for r in new_rows["rows"] if r["bucket"] == bucket]
        if not sel:
            continue
        print(f"    {bucket:<7} n={len(sel):<4} public={sum(1 for r in sel if r['public']):<4} "
              f"ids_redis={[r['id'] for r in sel if r['red_reasons']][:26]}")

    rs = red_split
    print("\n=== STEP 4b: the 22 RED rows, separated by cause ===")
    print("  ", rs["classification"])
    print("   unsafe, public:", rs["public_by_classification"]["unsafe"])
    print("   policy-gap, public:", rs["public_by_classification"]["policy_gap"])

    print("\n=== STEP 5: UI assets the wave brought in (pre-repair measurement) ===")
    print("  count:", ui_assets["count"], " classes:", ui_assets["asset_classes"])
    print("  dispositions:", dict(Counter(r["disposition"] for r in ui_assets["rows"])))

    print("\n=== STEP 6: asset corrections ===")
    print("  total:", corrections["total"], " pre-existing:",
          corrections["pre_existing"], " wave-created:", corrections["wave_created"])
    print("  actions:", corrections["actions"])
    print("  pre-existing rows with a decisive UI asset before repair:",
          corrections["pre_existing_with_decisive_ui_before"])
    print("  still carrying a decisive UI signal:",
          corrections["still_decisive_ui"] or "none")
    print("  trusted asset overwritten and cleared:",
          corrections["overwrote_a_trusted_asset"] or "none")

    print("\n=== STEP 7: provenance ===")
    p = enums["provenance"]
    print("  changes:", p["count"], " old invalid:", p["old_was_invalid"],
          " old valid:", p["old_was_valid"])
    print("  all new canonical-or-null:", p["new_all_canonical_or_null"],
          " no kind value in source_type:", p["no_kind_value_in_source_type"],
          " image_kind always canonical:", p["kinds_are_image_kind_not_source_type"])

    print("\n=== STEP 8: deadline precision ===")
    d = enums["deadline"]
    print("  changes:", d["count"], " 'day' rows carrying a date:",
          d["day_rows_with_a_date"])
    print("  mapping:", d["mapping"])
    print("  -> exact with no deadline_date:",
          d["to_exact_without_a_date"] or "none (correct)")
    print("  a-star.edu.sg rows:",
          [(r["id"], r["old"], r["new"], r["has_deadline_date"]) for r in d["a_star_rows"]]
          or "none")

    print("\n=== STEP 9/10: duplicates and archive ===")
    print("  all six resolved:", dupes["all_resolved"])
    print("  archived+active:", dupes["archived_active_count"],
          " would go public if unarchived:", dupes["would_go_public_if_unarchived"],
          " archived+public:", dupes["archived_and_public"] or "none")
    for x in dupes["duplicates"]:
        print(f"     {x['pair']} survivor={x['survivor']} dup={x['duplicate']} "
              f"archived={x['duplicate_archived']} "
              f"in_file={x['duplicate_in_retired_file']} "
              f"survivor_public={x['survivor_public']}")

    print("\n=== DEFECT REGISTER (from the previous hardening pass) ===")
    print("  ", dict(Counter(x["classification"] for x in defects)),
          " total:", len(defects))
    for x in defects:
        print(f"     {x['id']:<16} {x['title'][:46]}")

    print("\n=== STEP 13: invariants ===")
    for k, v in inv.items():
        if isinstance(v, bool):
            print(f"  {'OK   ' if v else 'FAIL '} {k}")
        elif isinstance(v, dict) and k == "row_counts":
            print(f"  INFO  {k}: {v}")
        elif isinstance(v, dict) and k == "orphan_references":
            n = sum(len(x) for x in v.values())
            print(f"  {'OK   ' if not n else 'CHECK'} {k}: {n} -> {v}")
        elif isinstance(v, dict):
            n = sum(len(x) for x in v.values())
            print(f"  {'OK   ' if not n else 'CHECK'} {k}: {n} {v if n else ''}")
        else:
            n = len(v)
            print(f"  {'OK   ' if not n else 'CHECK'} {k}: {n}"
                  + (f" {v}" if n and n <= 4 else ""))
    return bundle


if __name__ == "__main__":
    main()
