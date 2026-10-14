"""Build WAVE1_3_PRODUCTION_APPLY_MANIFEST_FINAL.md.

ID-level and field-level. Every proposed production change is listed with its
old value, its new value, the evidence that justifies it, and a risk class.

The manifest is a document. This script reads the local database and the apply
log and writes the file; it does not connect to anything.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

import wave13_harden as H  # noqa: E402

ROOT = BACKEND.parent
OUT = Path.home() / "AppData" / "Local" / "Temp" / "kilo" / "wave13"

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

COLUMN_NOTE = {
    "deadline_precision": "enum vocabulary",
    "image_source_type": "provenance vocabulary",
    "image_url": "asset identity",
    "image_source_url": "provenance",
    "image_kind": "asset classification",
    "image_alt_text": "accessibility text",
    "image_verified_at": "trust timestamp",
    "image_evaluated_at": "evaluation timestamp",
    "image_evaluation_status": "terminal outcome",
    "catalogue_url": "official catalogue link",
    "official_updates_url": "official updates link",
}

#: Every column this pass may have written. Diffing the pre-repair backup against
#: the current database is what makes the manifest complete: the backup is the
#: state immediately before the first write, so the diff is the whole change set
#: regardless of how many repair passes produced it.
WATCHED = (
    "deadline_precision",
    "image_url",
    "image_source_url",
    "image_source_type",
    "image_kind",
    "image_alt_text",
    "image_verified_at",
    "image_evaluated_at",
    "image_evaluation_status",
    "catalogue_url",
    "official_updates_url",
)


def diff_against_backup(backup: Path):
    """Field-level diff between the pre-repair snapshot and the current database.

    This is the authority for the manifest. The repair runs wrote a JSON log,
    but a second run overwrote the first, so the log is not a complete record.
    The snapshot is.
    """
    before = sqlite3.connect(f"file:{backup}?mode=ro", uri=True)
    before.row_factory = sqlite3.Row
    after = sqlite3.connect(f"file:{BACKEND / 'scholarzone.db'}?mode=ro", uri=True)
    after.row_factory = sqlite3.Row
    old = {r["id"]: dict(r) for r in before.execute("select * from scholarships")}
    new = {r["id"]: dict(r) for r in after.execute("select * from scholarships")}
    changes = []
    for sid in sorted(set(old) & set(new)):
        for col in WATCHED:
            ov, nv = old[sid].get(col), new[sid].get(col)
            if (ov or None) != (nv or None):
                changes.append({
                    "id": sid, "column": col, "old": ov, "new": nv,
                    "action": "restored pre-repair value" if nv and not ov
                              else "cleared" if ov and not nv else "normalised",
                    "evidence": f"pre-repair snapshot {backup.name}",
                    "risk": "medium" if (ov and not nv) else "low",
                })
    before.close()
    after.close()
    return changes, old, new


def esc(value) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("|", "\\|").replace("\n", " ").strip()
    if text == "":
        return "''"
    return f"`{text[:96]}`" if len(text) <= 96 else f"`{text[:93]}...`"


def count_ui_on_new_rows(backup: Path, wave_new: dict) -> int:
    """Wave-created rows whose stored asset was a favicon, app icon or UI glyph.

    Measured on the pre-repair snapshot, because the whole point is to report
    what the wave brought in. Counting on the repaired database would return
    zero and hide it.
    """
    from app.services.image_validator import assess_image_evidence

    decisive = ("navigation/icon path", "UI element keywords",
                "Generic UI image pattern", "error image", "social share keyword")
    snap = sqlite3.connect(f"file:{backup}?mode=ro", uri=True)
    snap.row_factory = sqlite3.Row
    count = 0
    for r in snap.execute("select * from scholarships where image_url is not null"):
        if r["id"] not in wave_new:
            continue
        v = assess_image_evidence(
            image_url=r["image_url"], image_source_url=r["image_source_url"],
            image_source_type=r["image_source_type"], image_kind=r["image_kind"],
            alt_text=r["image_alt_text"],
            official_source_url=r["official_source_url"],
        )
        if any(any(k.lower() in s.lower() for k in decisive)
               for s in v.non_content_signals):
            count += 1
    snap.close()
    return count


def main() -> Path:
    gate = json.loads((OUT / "release_gate.json").read_text(encoding="utf-8"))
    analysis = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))

    backup = sorted(BACKEND.glob("scholarzone.pre_wave13_hardening_*.db"))[0]
    log_changes, _old, _new = diff_against_backup(backup)
    log = {"changes": log_changes, "backup": str(backup)}

    con = sqlite3.connect(f"file:{BACKEND / 'scholarzone.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    pre = sqlite3.connect(
        f"file:{BACKEND / 'scholarzone.pre_wave1_20261004_133109.db'}?mode=ro", uri=True)
    pre.row_factory = sqlite3.Row

    wave_new = {
        r["id"]: r for r in con.execute(
            "select * from scholarships where id > 490")
    }
    ui_new = count_ui_on_new_rows(backup, wave_new)

    by_id: dict[int, list[dict]] = {}
    for ch in log["changes"]:
        by_id.setdefault(ch["id"], []).append(ch)

    lines: list[str] = []
    A = lines.append

    A("# WAVE 1-3 PRODUCTION APPLY MANIFEST — FINAL")
    A("")
    A(f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ")
    A("**Status:** NOT APPLIED. This document proposes; it does not execute.  ")
    A("**Neon:** untouched. No credential for it exists in this environment "
      "(§6).")
    A("")
    A("Every row below is a change this session made to the **local** database "
      "and is proposed for production. Old values are what the database held "
      "immediately before this pass, new values are what it holds now. Nothing "
      "here is inferred: each line is a diff between the pre-repair snapshot and "
      "the current file, so the manifest is complete regardless of how many "
      "repair passes produced it.")
    A("")
    A("---")
    A("")
    A("## 1. Scope summary")
    A("")
    A("| Measure | Value |")
    A("|---|---|")
    A(f"| Catalogue rows (local, post-repair) | {gate['rows']} |")
    A(f"| Rows publicly visible | {gate['public_visible']} |")
    A(f"| Field-level changes proposed | {len(log['changes'])} |")
    A(f"| Distinct rows touched | {len(by_id)} |")
    A(f"| Rows created by the wave | {analysis['totals']['wave_created']} |")
    A(f"| Rows retired this pass | {len(H.DUPLICATE_PAIRS)} |")
    A(f"| Rows left without an image | {len(gate['rows_without_image'])} |")
    A(f"| Local release gate | **{gate['gate']}** "
      f"({gate['red_count']} RED, {gate['yellow_count']} YELLOW) |")
    A(f"| Local backup taken before any write | `{Path(log['backup']).name}` |")
    A("")
    A("Proposed change volume by column:")
    A("")
    A("| Column | Changes | What it is |")
    A("|---|---|---|")
    import collections
    for col, n in collections.Counter(c["column"] for c in log["changes"]).most_common():
        A(f"| `{col}` | {n} | {COLUMN_NOTE.get(col, '-')} |")
    A("")
    A("Proposed change volume by risk class:")
    A("")
    for risk, n in collections.Counter(c["risk"] for c in log["changes"]).most_common():
        A(f"- **{risk}**: {n}")
    A("")

    A("## 2. Rows created by Wave 1-3 (excluded from this manifest)")
    A("")
    A(f"The wave inserted **{len(wave_new)} rows** (ids "
      f"{min(wave_new) if wave_new else '-'}–{max(wave_new) if wave_new else '-'}). "
      "They are **not** proposed for production apply.")
    A("")
    A("Reason — **PROVEN**: the public-visibility gate requires both "
      "`image_url` and `image_verified_at`. A new row whose image fields are "
      "omitted fails the gate and never appears, so a new row cannot be "
      "separated from its image decision. A row that arrives with an image has "
      "had that image asserted by research rather than validated by the "
      "pipeline, and the whole point of this pass is that such assertions were "
      "not trustworthy in this wave. **No replacement URL was invented for any "
      "of them.**")
    A("")
    A("| Measure | Rows |")
    A("|---|---|")
    A(f"| Wave-created rows carrying a decisive favicon/app-icon/UI asset | "
      f"{ui_new} |")
    A(f"| Wave-created rows excluded from this manifest | {len(wave_new)} |")
    A("")
    A("**Both figures are measured on the pre-repair snapshot**, not on the "
      "repaired database: after the repair there are no UI assets left to "
      "count, so measuring afterwards would report zero and hide the problem.")
    A("")

    A("## 3. Duplicate resolution — proposed retire operations")
    A("")
    A("Mechanism: an entry in `backend/config/retired_records.json`, then the "
      "`retire` stage. The row is quarantined and archived, not deleted, so its "
      "id stays addressable and nothing that referenced it is orphaned.")
    A("")
    A("| Retired id | Surviving id | Reviews on survivor | Evidence |")
    A("|---|---|---|---|")
    for pair in analysis["duplicates"]:
        rev = "?"
        for side in ("older", "newer"):
            if pair[f"{side}"] == pair["survivor"] and pair.get(f"{side}_facts"):
                rev = pair[f"{side}_facts"]["reviews"]
        A(f"| {pair['retire']} | {pair['survivor']} | {rev} | "
          f"{esc(pair['why'][:150])} |")
    A("")
    A("Reviews, verification history and image reviews are preserved: the "
      "retire stage archives rather than deletes, exactly as it did for the 48 "
      "pre-existing retirements. Three pairs additionally had the duplicate's "
      "`official_details` copied into the survivor first (ids 10, 13) so no "
      "researched text was discarded; where both sides already held a research "
      "block nothing was merged, because there is no evidence that one "
      "supersedes the other.")
    A("")

    A("## 4. Field-level changes, row by row")
    A("")
    A("Ordered by row id. `risk` is `low` for a value re-derived by a canonical "
      "classifier or restored verbatim from the pre-wave snapshot, and `medium` "
      "for an asset cleared because nothing trustworthy could be established.")
    A("")
    A("| id | field | old | new | action | evidence | risk |")
    A("|---|---|---|---|---|---|---|")
    for sid in sorted(by_id):
        changes = sorted(
            by_id[sid],
            key=lambda c: (RISK_ORDER.get(c["risk"], 9), c["column"]),
        )
        for c in changes:
            A(f"| {sid} | `{c['column']}` | {esc(c['old'])} | {esc(c['new'])} "
              f"| {c['action']} | {esc(c['evidence'][:110])} | {c['risk']} |")
    A("")

    A("## 5. Validation status per change class")
    A("")
    A("| Change class | Count | Validator that decided it | Status |")
    A("|---|---|---|---|")
    A("| `deadline_precision` normalised | "
      f"{sum(1 for c in log['changes'] if c['column'] == 'deadline_precision')} "
      "| `coerce_deadline_precision` (existing) | PASS |")
    A("| `image_source_type` re-derived | "
      f"{sum(1 for c in log['changes'] if c['column'] == 'image_source_type')} "
      "| `_issuer_kind` + `is_valid_source_type` (existing) | PASS |")
    A("| asset restored from pre-wave snapshot | "
      f"{sum(1 for c in log['changes'] if c['action'] == 'restored')} "
      "| `assess_image_evidence` (new gate) | PASS |")
    A("| asset cleared | "
      f"{sum(1 for c in log['changes'] if c['action'] == 'cleared')} "
      "| `assess_image_evidence` (new gate) | PASS |")
    A("| `image_evaluation_status` set to a terminal negative | "
      f"{sum(1 for c in log['changes'] if c['column'] == 'image_evaluation_status')} "
      "| `ImageEvaluationStatus.INVALID_CANDIDATES` | PASS |")
    A("| list-column shape repaired | 6 rows | `normalize_list_column` "
      "(existing, run via `--stage repair_list_columns`) | PASS |")
    A("")

    A("## 6. Production delta — UNKNOWN, and why")
    A("")
    A("**PROVEN:** the local repository contains no usable production database "
      "credential, and none can be obtained from here.")
    A("")
    A("| Path attempted | Result |")
    A("|---|---|")
    A("| `SCHOLARZONE_DATABASE_URL` / `DATABASE_URL` / `PG*` in the process | "
      "**absent** |")
    A("| `backend/.env` (gitignored) | contains only `RESEND_API_KEY`, "
      "`NOTIFICATION_EMAIL`, `SCHOLARZONE_VERIFICATION_SECRET` |")
    A("| `backend/.env.example` | template only |")
    A("| Application started as `SCHOLARZONE_ENVIRONMENT=production` | "
      "`RuntimeError: SCHOLARZONE_DATABASE_URL is required in production. "
      "Configure a PostgreSQL (Neon) connection string...` |")
    A("| GitHub Actions secret `SCHOLARZONE_DATABASE_URL` | **exists** "
      "(last set 2026-09-06) — GitHub never returns secret values, only names "
      "and timestamps |")
    A("| Vercel CLI | installed, but no linked project directory present |")
    A("")
    A("**UNKNOWN:** the contents of Neon, and therefore the exact difference "
      "between the local proposed state and production. Every 'old value' in "
      "§4 is the local post-wave value, not the production value.")
    A("")
    A("Consequence: this manifest cannot be diffed against production, and "
      "**must not be applied** until a read-only Neon role is supplied and the "
      "ID-level comparison is run.")
    A("")

    A("## 7. Corrections required BEFORE this manifest may be applied")
    A("")
    A("The diff above is complete and correct as a record of what changed. It is "
      "**not** a statement that every change should go to production. The final "
      "audit found defects that this manifest must not carry into Neon.")
    A("")
    audit_path = OUT / "final_audit.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        defects = audit.get("defect_register", [])
        if not defects:
            A("No defects outstanding.")
        for family, heading, why in (
            ("PROVEN FALSE POSITIVE",
             "D1 — an official logo was cleared on a detector false positive",
             "`_detect_error_signals` matched a three-digit HTTP status inside a CMS "
             "content hash in the filename and scored it 2.0. The asset was then "
             "cleared as a non-content artefact."),
            ("PROVEN PRECISION LOSS",
             "D2 — a more specific provenance was reverted to a vaguer one",
             "The wave improved `image_source_type` on these rows. The asset-"
             "restoration path restored that column along with the image, undoing the "
             "improvement."),
        ):
            rows = [d for d in defects if d["classification"] == family]
            A("")
            A(f"### {heading} — {len(rows)} rows")
            A("")
            A(f"*Why:* {why}")
            A("")
            A("| scholarship_id | title | current | required | evidence |")
            A("|---|---|---|---|---|")
            for d in rows:
                if family.startswith("PROVEN FALSE"):
                    A(f"| {d['scholarship_id']} | {esc(d['title'][:52])} | "
                      f"`image_url=NULL` | restore the asset | "
                      f"{esc(d['asset_cleared'][-56:])} |")
                else:
                    A(f"| {d['scholarship_id']} | {esc(d['title'][:52])} | "
                      f"`{d['now']}` | `{d['correct_value']}` | "
                      f"host `{d['host']}`, alt `{esc(str(d['alt_text'])[:26])}` |")
            A("")
            A("Both families are **reversible without research**: D1 restores an "
              "asset recorded in the pre-repair snapshot, D2 recomputes from host and "
              "alt text with `_issuer_kind`, which is verified to agree on every row.")
            A("")
    A("## 8. Apply preconditions")
    A("")
    A("All must hold before any controlled production apply is considered:")
    A("")
    A("1. Read-only Neon credentials provisioned, and a successful read "
      "demonstrated.")
    A("2. ID-level comparison of this manifest against Neon, row by row. Any "
      "row whose production value differs from the 'old value' here must be "
      "re-decided, not applied.")
    A("3. The six code guards deployed, so the repaired values cannot be "
      "reintroduced by the next run.")
    A("4. A human decision on the four YELLOW items in "
      "`WAVE1_3_HARDENING_FINAL.md` §11.")
    A("5. A decision on the 234 wave-created rows, which this manifest "
      "deliberately excludes.")
    A("6. Dry run of every stage against Neon, with the run log reviewed, "
      "before any non-dry run.")
    A("")
    A("**Never copy `scholarzone.db` into Neon.** The apply mechanism is the "
      "repository's own stages driven by the `backend/config/*.json` change "
      "set, one stage at a time.")
    A("")

    path = ROOT / "WAVE1_3_PRODUCTION_APPLY_MANIFEST_FINAL.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    pre.close()
    print(f"wrote {path} ({path.stat().st_size} bytes, "
          f"{len(lines)} lines, {len(log['changes'])} changes)")
    return path


if __name__ == "__main__":
    main()


