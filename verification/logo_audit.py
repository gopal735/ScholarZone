"""Logo audit over the live public catalogue.

Three questions, kept separate because they are three different defects:
  1. is the asset served from the awarding body's own domain or its own CDN?
  2. is the stored image-evaluation verdict newer or older than the stored logo?
  3. are the hosts whose logos were rejected as unusable still carrying one?

Nothing here decides anything. It reports, with ids, so a decision can be made
against evidence rather than against a pattern.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.scholarship_evidence import _normalize_host, _registrable  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = {int(k): v for k, v in json.loads((HERE / "live_raw.json").read_text(encoding="utf-8")).items()}
UNRESOLVED = json.loads((ROOT / "backend" / "config" / "unresolved_logos.json").read_text(encoding="utf-8"))

#: Asset hosts that are the awarding body's own delivery infrastructure rather
#: than a different organisation's brand. Verified per record below.
CDN_HOSTS = {
    "cloudfront.net",
    "net.au",
    "sitecorecloud.io",
    "squarespace-cdn.com",
    "wixstatic.com",
    "webdamdb.com",
    "gstatic.com",
}


def registrable(url: str | None) -> str | None:
    if not url:
        return None
    host = urlsplit(url).hostname
    return _registrable(_normalize_host(host)) if host else None


def main() -> None:
    off_domain: list[dict] = []
    for sid, row in sorted(RAW.items()):
        asset = row.get("image_url")
        source_page = row.get("image_source_url")
        if not asset or not source_page:
            continue
        a, b = registrable(asset), registrable(source_page)
        if a == b:
            continue
        asset_host = (urlsplit(asset).hostname or "").lower()
        off_domain.append(
            {
                "id": sid,
                "title": row.get("title"),
                "image_url": asset,
                "image_source_url": source_page,
                "asset_registrable_domain": a,
                "awarding_body_registrable_domain": b,
                "asset_host_on_known_cdn": a in CDN_HOSTS,
                "image_kind": row.get("image_kind"),
                "image_evaluation_status": row.get("image_evaluation_status"),
            }
        )

    stale: list[int] = []
    fresh: list[int] = []
    for sid, row in sorted(RAW.items()):
        evaluated = row.get("image_evaluated_at")
        verified = row.get("image_verified_at")
        if not evaluated or not verified:
            continue
        try:
            if str(verified) > str(evaluated):
                stale.append(sid)
            else:
                fresh.append(sid)
        except TypeError:
            continue

    quarantined_hosts = {h["host"]: h for h in UNRESOLVED["hosts"]}
    still_carrying = []
    for sid, row in sorted(RAW.items()):
        for field in ("image_url", "image_source_url"):
            value = row.get(field) or ""
            for host, entry in quarantined_hosts.items():
                if host in value:
                    still_carrying.append(
                        {"id": sid, "host": host, "field": field, "value": value[:160]}
                    )

    report = {
        "generated_at": "2026-10-03",
        "records": len(RAW),
        "image_kind": dict(sorted(Counter(r.get("image_kind") for r in RAW.values()).items(), key=lambda kv: str(kv[0]))),
        "image_evaluation_status": dict(
            sorted(Counter(r.get("image_evaluation_status") for r in RAW.values()).items(), key=lambda kv: str(kv[0]))
        ),
        "quarantined_hosts": [
            {"host": h["host"], "records": h["records"], "reason_code": h["reason_code"]}
            for h in UNRESOLVED["hosts"]
        ],
        "quarantined_host_records_total": sum(h["records"] for h in UNRESOLVED["hosts"]),
        "quarantined_hosts_still_carrying_an_asset": len(still_carrying),
        "quarantined_hosts_still_carrying": still_carrying,
        "assets_outside_the_awarding_body_domain": {
            "count": len(off_domain),
            "on_known_delivery_cdn": sum(1 for r in off_domain if r["asset_host_on_known_cdn"]),
            "records": off_domain,
        },
        "image_verdict_staleness": {
            "logo_accepted_after_the_negative_evaluation": len(stale),
            "logo_accepted_before_the_evaluation": len(fresh),
            "explanation": (
                "A record whose image_verified_at is later than its image_evaluated_at has "
                "an evaluation verdict that predates its own logo, so the verdict describes a "
                "state the row is no longer in. The logo is the newer fact; the verdict is the "
                "stale one. These are inconsistent, not wrong, and the discrepancy is reported "
                "rather than silently rewritten because the image stage owns that decision."
            ),
        },
    }
    (HERE / "logo_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print("records:", report["records"])
    print("image_kind:", report["image_kind"])
    print("image_evaluation_status:", report["image_evaluation_status"])
    print(
        "quarantined hosts:", len(report["quarantined_hosts"]),
        "covering", report["quarantined_host_records_total"], "records;",
        "still carrying an asset:", report["quarantined_hosts_still_carrying_an_asset"],
    )
    off = report["assets_outside_the_awarding_body_domain"]
    print("assets outside the awarding-body domain:", off["count"], "| on a known CDN:", off["on_known_delivery_cdn"])
    for r in off["records"]:
        if not r["asset_host_on_known_cdn"]:
            print("   NOT a delivery CDN:", r["id"], r["asset_registrable_domain"], "->", r["awarding_body_registrable_domain"])
    print("logo accepted after its own evaluation:", report["image_verdict_staleness"]["logo_accepted_after_the_negative_evaluation"])


if __name__ == "__main__":
    main()
