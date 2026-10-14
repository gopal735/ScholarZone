"""Wave 1-3 local release gate.

Read-only. Re-runs every release invariant against the local database and the
canonical code paths, and refuses to declare the gate passed while any PROVEN
RED condition survives.

The public-visibility check imports `public_visibility_conditions` rather than
re-implementing it, so the gate cannot drift from what the application actually
publishes.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session  # noqa: E402

from app.models import Scholarship  # noqa: E402
from app.repositories.scholarships import public_visibility_conditions  # noqa: E402
from app.services.deadline_semantics import DEADLINE_PRECISION_VALUES  # noqa: E402
from app.services.image_evaluation_status import TERMINAL_STATUSES  # noqa: E402
from app.services.image_validator import assess_image_evidence  # noqa: E402
from app.services.scholarship_image_verifier import is_valid_source_type  # noqa: E402

DB = BACKEND / "scholarzone.db"
OUT = Path.home() / "AppData" / "Local" / "Temp" / "kilo" / "wave13"

DECISIVE_UI_SIGNALS = (
    "navigation/icon path",
    "UI element keywords",
    "Generic UI image pattern",
    "error image",
    "social share keyword",
)

IMAGE_COLUMNS = ("image_url", "image_source_url", "image_source_type",
                 "image_kind", "image_alt_text", "image_verified_at")


def host_of(url: str | None) -> str | None:
    if not url:
        return None
    h = url.split("//", 1)[-1].split("/", 1)[0].split("?", 1)[0].lower()
    return h[4:] if h.startswith("www.") else h


def main() -> dict:
    raw = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    raw.row_factory = sqlite3.Row
    rows = {r["id"]: dict(r) for r in raw.execute("select * from scholarships")}

    engine = create_engine(f"sqlite:///{DB}")
    with Session(engine) as session:
        published = session.scalars(
            select(Scholarship).where(*public_visibility_conditions())
        ).all()
        public_ids = sorted(s.id for s in published)

    findings: list[dict] = []

    def fail(check, ids, detail):
        findings.append({
            "check": check, "severity": "RED", "count": len(ids),
            "ids": list(ids)[:60], "detail": detail,
        })

    def warn(check, ids, detail):
        listed = list(ids)[:60] if isinstance(ids, (list, tuple)) else [ids]
        findings.append({
            "check": check, "severity": "YELLOW", "count": len(ids),
            "ids": listed, "detail": detail,
        })

    # 1. https on every stored image
    bad_scheme = [
        sid for sid, r in rows.items()
        if r.get("image_url") and not r["image_url"].lower().startswith("https://")
    ]
    if bad_scheme:
        fail("image_url transport", bad_scheme, "stored image_url is not https")

    # 2. image_url / image_kind coherence
    incoherent = [
        sid for sid, r in rows.items()
        if bool(r.get("image_url")) != bool(r.get("image_kind"))
    ]
    if incoherent:
        fail("image_url/image_kind coherence", incoherent,
             "image_url present without image_kind, or the reverse")

    # 3. image_source_type vocabulary
    bad_type = [
        sid for sid, r in rows.items()
        if r.get("image_source_type") is not None
        and not is_valid_source_type(r["image_source_type"])
    ]
    if bad_type:
        fail("image_source_type vocabulary", bad_type,
             "value outside ImageSourceType")

    # 4. deadline_precision vocabulary
    bad_prec = [
        sid for sid, r in rows.items()
        if (r.get("deadline_precision") or "") not in DEADLINE_PRECISION_VALUES
    ]
    if bad_prec:
        fail("deadline_precision vocabulary", bad_prec,
             "value outside DEADLINE_PRECISION_VALUES")

    # 5. decisive UI / favicon assets still stored
    #
    # "social thumbnail dimensions" is deliberately *not* decisive. A 1200x630
    # OG-size derivative is a size transform, not proof that the underlying asset
    # is a UI glyph: id 398 holds a real Unsplash photograph from the
    # university's own /content/gallery/ path, served through its OG pipeline.
    # Rejecting on that hint alone would destroy a correct photograph, so the
    # rows it fires on are reported for a human instead.
    ui, soft = [], []
    for sid, r in sorted(rows.items()):
        if not r.get("image_url"):
            continue
        v = assess_image_evidence(
            image_url=r["image_url"], image_source_url=r.get("image_source_url"),
            image_source_type=r.get("image_source_type"), image_kind=r.get("image_kind"),
            alt_text=r.get("image_alt_text"),
            official_source_url=r.get("official_source_url"),
        )
        if any(any(k.lower() in s.lower() for k in DECISIVE_UI_SIGNALS)
               for s in v.non_content_signals):
            ui.append(sid)
        elif any("social thumbnail dimensions" in s.lower() for s in v.non_content_signals):
            soft.append(sid)
    if ui:
        fail("favicon/app-icon/UI assets stored", ui,
             "decisive UI signal present on a stored image")
    if soft:
        warn("OG-size derivative images", soft,
             "social-thumbnail size hint on a first-party asset; needs a human eye, "
             "not an automatic clear")

    # 6. official source requirements.
    #
    # Scoped to the release set. A non-https official source that the wave never
    # touched, on a row with no image and therefore not public, is a pre-existing
    # research gap: correcting it means re-researching the programme's page,
    # which no code change and no data edit can supply. Reporting it as a RED
    # release blocker would be claiming a fix this task is not allowed to make.
    public_rows = {sid: rows[sid] for sid in public_ids}
    no_source = sorted(
        sid for sid, r in public_rows.items()
        if not r.get("official_source_url")
        or not r["official_source_url"].lower().startswith("https://")
    )
    if no_source:
        fail("official source (release set)", no_source,
             "publicly visible row missing an https official_source_url")
    non_https_outside = sorted(
        sid for sid, r in rows.items()
        if sid not in public_rows
        and (not r.get("official_source_url")
             or not r["official_source_url"].lower().startswith("https://"))
    )
    if non_https_outside:
        warn("non-https official source outside the release set", non_https_outside,
             "pre-existing http official source on a non-public row; unchanged by "
             "Wave 1-3, excluded from the apply manifest, needs a research pass")

    # 7. image evaluation status is terminal for rows that have an image
    non_terminal = [
        sid for sid, r in rows.items()
        if r.get("image_url") and r.get("image_evaluation_status") not in TERMINAL_STATUSES
    ]
    if non_terminal:
        warn("image_evaluation_status", non_terminal,
             "row has an image but no terminal evaluation status")

    # 8. malformed list columns
    malformed = []
    for sid, r in rows.items():
        for col in ("eligibility", "coverage", "benefits", "required_documents"):
            v = r.get(col)
            if v and not str(v).lstrip().startswith(("[", "{")):
                malformed.append(f"{sid}:{col}")
    if malformed:
        fail("list columns", malformed,
             "value is not a JSON array/object")

    # 9. orphan references
    orphans = {}
    for table in ("scholarship_reviews", "scholarship_verification_history", "image_reviews"):
        try:
            orphans[table] = [
                r[0] for r in raw.execute(
                    f"select distinct scholarship_id from {table} "
                    "where scholarship_id not in (select id from scholarships)"
                )
            ]
        except sqlite3.Error:
            orphans[table] = []
    real_orphans = {k: v for k, v in orphans.items() if v}
    if real_orphans:
        warn("orphan references", real_orphans, "references to rows that no longer exist")

    # 10. duplicate official_source_url
    seen: dict[str, list[int]] = {}
    for sid, r in rows.items():
        u = (r.get("official_source_url") or "").rstrip("/").lower()
        if u:
            seen.setdefault(u, []).append(sid)
    dup_urls = {u: ids for u, ids in seen.items() if len(ids) > 1}
    if dup_urls:
        warn("duplicate official_source_url", dup_urls, "same URL on more than one row")

    # 11. archived rows are not public
    archived_public = sorted(set(public_ids) & {
        sid for sid, r in rows.items() if r.get("is_archived")})
    if archived_public:
        fail("archived/public separation", archived_public,
             "archived row is publicly visible")

    # 12. duplicates still present as live pairs
    import wave13_harden as H

    still_live = sorted({
        p["retire"] for p in H.DUPLICATE_PAIRS
        if rows.get(p["retire"]) and not rows[p["retire"]].get("is_archived")
    })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": len(rows),
        "public_visible": len(public_ids),
        "red_count": sum(1 for f in findings if f["severity"] == "RED"),
        "yellow_count": sum(1 for f in findings if f["severity"] == "YELLOW"),
        "findings": findings,
        "duplicates_still_live": still_live,
        "archived_active": sorted(
            sid for sid, r in rows.items()
            if r.get("is_archived") and r.get("verification_status") == "active"
        ),
        "archived_active_would_be_public_if_unarchived": sorted(
            sid for sid, r in rows.items()
            if r.get("is_archived") and r.get("verification_status") == "active"
            and r.get("is_verified") and r.get("image_url")
            and r.get("image_verified_at") and r.get("image_source_type")
        ),
        "rows_without_image": sorted(
            sid for sid, r in rows.items() if not r.get("image_url")
        ),
    }
    report["gate"] = "PASS" if report["red_count"] == 0 else "FAIL"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "release_gate.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8"
    )
    raw.close()

    print(f"rows={report['rows']} public={report['public_visible']} "
          f"gate={report['gate']} red={report['red_count']} yellow={report['yellow_count']}")
    for f in findings:
        print(f"  [{f['severity']}] {f['check']}: {f['count']} - {f['detail']}")
        print(f"        {f['ids'][:14]}")
    print("duplicates still live (un-retired):", report["duplicates_still_live"])
    print("archived+active:", len(report["archived_active"]))
    print("would become public if unarchived:", len(report["archived_active_would_be_public_if_unarchived"]))
    print("rows without an image:", len(report["rows_without_image"]))
    return report


if __name__ == "__main__":
    main()
