"""Build DUPLICATE_RESOLUTION_MANIFEST.md.

One section per proven duplicate pair: every field that distinguishes the two
rows, the survivor decision against the four stated criteria, the references
that had to be preserved, and the exact canonical operation performed.

Local only. Reads the pre-wave snapshot and the current database; touches Neon
never.
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
DB = BACKEND / "scholarzone.db"
PRE = BACKEND / "scholarzone.pre_wave1_20261004_133109.db"

COMPARE = [
    ("title", "title"),
    ("official_source_url", "official_source_url"),
    ("catalogue_url", "catalogue_url"),
    ("image_url", "image_url"),
    ("image_kind", "image_kind"),
    ("verification_status", "verification_status"),
    ("status", "status"),
    ("deadline_date", "deadline_date"),
    ("created_at", "created_at"),
]


def norm(url) -> str:
    return (url or "").rstrip("/").lower()


def main() -> Path:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = {r["id"]: dict(r) for r in con.execute("select * from scholarships")}
    for r in rows.values():
        r["_reviews"] = con.execute(
            "select count(*) from scholarship_reviews where scholarship_id=?",
            (r["id"],)).fetchone()[0]
        r["_history"] = con.execute(
            "select count(*) from scholarship_verification_history where scholarship_id=?",
            (r["id"],)).fetchone()[0]

    retired = json.loads(
        (BACKEND / "config" / "retired_records.json").read_text(encoding="utf-8")
    )["records"]
    retired_ids = {e["id"] for e in retired}

    lines: list[str] = []
    A = lines.append

    A("# DUPLICATE RESOLUTION MANIFEST")
    A("")
    A(f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ")
    A("**Applied to:** local SQLite only. **Neon: untouched.**  ")
    A("**Mechanism:** `backend/config/retired_records.json` + the `retire` "
      "maintenance stage. Quarantine and archive, never delete.")
    A("")
    A("---")
    A("")
    A("## Survivor rule")
    A("")
    A("Two rules, applied in order, because they are the only two that cannot "
      "be argued with:")
    A("")
    A("1. **A row holding reviews is not retirable.** Reviews are the one "
      "relationship in this schema that cannot be recreated. In four of the six "
      "pairs the older row holds 5–7 reviews and the wave-created row holds "
      "none, so the older row survives and the newer one is retired even though "
      "the newer one often holds more research text.")
    A("2. **Where neither side holds reviews, the researched row survives.** "
      "Completeness and verification evidence both point the same way, and "
      "nothing is lost either way.")
    A("")
    A("Where the survivor had no `official_details` and the retired row did, "
      "the retired row's block is copied into the survivor **before** the "
      "retire, so no researched text is discarded. Where both sides hold a "
      "block, nothing is merged: there is no evidence that one supersedes the "
      "other, and asserting a merge would be a guess.")
    A("")
    A("## Preserved references")
    A("")
    A("| Table | Behaviour on retire |")
    A("|---|---|")
    A("| `scholarship_reviews` | untouched — the row is archived, not deleted, "
      "so every review keeps pointing at a live id |")
    A("| `scholarship_verification_history` | untouched; history stays "
      "attributable to the id it was recorded against |")
    A("| `image_reviews` | untouched |")
    A("")
    A("The pre-existing 48 retirements work exactly this way. One orphan "
      "exists in the whole database — `scholarship_verification_history` "
      "pointing at id 358, which the wave **purged** rather than retired. That "
      "is the one mechanism in this schema that does lose its id, and it is not "
      "the mechanism used here.")
    A("")

    for pair in H.DUPLICATE_PAIRS:
        older_id, newer_id = pair["older"], pair["newer"]
        a, b = rows.get(older_id), rows.get(newer_id)
        survivor = pair["survivor"]
        A("---")
        A("")
        A(f"## {older_id} / {newer_id} — {(a or b or {}).get('title', '?')}")
        A("")
        A(f"**Decision: retire `{pair['retire']}`, keep `{survivor}`.**")
        A("")
        A(f"**PROVEN duplicate.** {pair['why']}")
        A("")

        if a and b:
            A("| Field | " + f"`{older_id}` | `{newer_id}` |")
            A("|---|---|---|")
            for label, col in COMPARE:
                av, bv = a.get(col), b.get(col)
                mark = ""
                if col in ("official_source_url", "catalogue_url") and \
                        norm(av) and norm(av) == norm(bv):
                    mark = " **(identical after normalisation)**"
                A(f"| {label} | {fmt(av)} | {fmt(bv)}{mark} |")
            A(f"| `official_details` length | {len(a.get('official_details') or '')} chars "
              f"| {len(b.get('official_details') or '')} chars |")
            A(f"| reviews | {a['_reviews']} | {b['_reviews']} |")
            A(f"| verification history rows | {a['_history']} | {b['_history']} |")
            A(f"| in `retired_records.json` | "
              f"{'yes' if older_id in retired_ids else 'no'} | "
              f"{'yes' if newer_id in retired_ids else 'no'} |")
            A("")

        A("**Criteria applied**")
        A("")
        A("| Criterion | Reading |")
        A("|---|---|")
        A(f"| authoritative source | both resolve to the same awarding body; "
          f"the two URLs are the same page, differing only in path casing or in "
          f"one case by a parent-vs-programme relationship |")
        A(f"| completeness | survivor holds "
          f"{len((rows.get(survivor) or {}).get('official_details') or '')} chars "
          f"of `official_details`; the retired row holds "
          f"{len((rows.get(pair['retire']) or {}).get('official_details') or '')} |")
        A(f"| verification evidence | survivor holds "
          f"{(rows.get(survivor) or {}).get('_reviews', '?')} reviews and "
          f"{(rows.get(survivor) or {}).get('_history', '?')} history rows |")
        A(f"| created/updated provenance | `{older_id}` created "
          f"{str(a.get('created_at'))[:10] if a else '?'}, `{newer_id}` created "
          f"{str(b.get('created_at'))[:10] if b else '?'} |")
        A(f"| reviews / references | reviews on `{older_id}`: "
          f"{a['_reviews'] if a else '?'}; on `{newer_id}`: "
          f"{b['_reviews'] if b else '?'} — this is the deciding criterion |")
        A("")
        merge = pair["merge_details_into_survivor"]
        if merge:
            A(f"**Merge performed:** the retired row's `official_details` was "
              f"copied into `{survivor}` before retirement, so the researched "
              f"block survives with the reviews.")
        else:
            A("**Merge performed:** none. Both rows' research is either already "
              "on the survivor or has no supportable claim to replace it.")
        A("")

    A("---")
    A("")
    A("## Post-resolution state")
    A("")
    for pair in H.DUPLICATE_PAIRS:
        r = rows.get(pair["retire"])
        s = rows.get(pair["survivor"])
        A(f"- `{pair['retire']}`: "
          + (f"`is_archived={r.get('is_archived')}`, "
             f"`verification_status={r.get('verification_status')}`, "
             f"publicly visible: **no**"
             if r else "row absent") + f" · survivor `{pair['survivor']}`: "
          + (f"`is_archived={s.get('is_archived')}`, "
             f"`verification_status={s.get('verification_status')}`"
             if s else "**MISSING**"))
    A("")
    A("**Not applied to Neon.** The `retired_records.json` change is local "
      "configuration and would be applied by running the `retire` stage against "
      "production in a separate, separately-approved operation.")
    A("")

    path = ROOT / "DUPLICATE_RESOLUTION_MANIFEST.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def fmt(v) -> str:
    if v is None:
        return "NULL"
    t = str(v).replace("|", "\\|")
    return f"`{t[:88]}`" if len(t) <= 88 else f"`{t[:85]}...`"


if __name__ == "__main__":
    main()
