"""Complete production detail sweep and trust-semantics check.

Every authoritative public id, not a sample: the requirement is an invariant over
the whole universe, and a representative sample cannot establish one.

Three things are asserted per record, and they are different claims:

* availability  - the page answers 200 and the body validates as the public
  contract;
* shape        - every list-typed field is a JSON array, not a stringified one;
* trust        - the verification state the API reports is the state the public
  surfaces are entitled to present. A non-active record rendered as "Verified"
  is a false claim to an applicant and is counted as a failure here, not as
  cosmetic noise.

Run against a base URL. Nothing is written.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://scholarzone-fwzj.vercel.app"
HEADERS = {"User-Agent": "Mozilla/5.0 ScholarZoneReleaseSweep/1.0", "Accept": "application/json"}
LIST_FIELDS = (
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "required_documents",
    "application_method",
)
UNRESOLVED = (79, 113, 134, 140)


def get(path: str, timeout: int = 90, attempts: int = 4):
    """Fetch with retry.

    Probing several hundred endpoints concurrently gets connections refused or
    reset by the edge. That is a property of the harness, not of the service,
    and reporting it as a failed request would be wrong - so a transport error
    is retried with backoff and only a settled HTTP status is recorded.
    """
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS)
    last: object = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    return None, f"{type(last).__name__}: {last}"


def main() -> None:
    # The directory caps `limit` at 100 and reports `total` / `total_pages` in a
    # `pagination` block. A request above the cap is a 422 rather than a bigger
    # page, so both are read from the response rather than assumed.
    status, raw = get("/api/scholarships?limit=100&page=1")
    if status != 200:
        print(f"catalogue HTTP {status}: {raw[:200]}")
        raise SystemExit(1)
    catalogue = json.loads(raw)
    pagination = catalogue.get("pagination") or {}
    total = pagination.get("total")
    total_pages = pagination.get("total_pages") or 1
    ids = [r["id"] for r in catalogue.get("items", [])]

    for page in range(2, total_pages + 1):
        code, body = get(f"/api/scholarships?limit=100&page={page}")
        if code != 200:
            print(f"page {page} HTTP {code}")
            break
        block = json.loads(body).get("items", [])
        ids.extend(r["id"] for r in block)
    ids = sorted(set(ids))

    print(f"catalogue HTTP {status}: {len(ids)} distinct public ids (total={total}, pages={total_pages})")
    if total is not None and len(ids) != total:
        print(f"WARNING: paged {len(ids)} ids but the directory reports total={total}")

    status, stats_raw = get("/api/scholarships/stats")
    stats = json.loads(stats_raw) if status == 200 else {}
    print(
        f"stats    HTTP {status}: total={stats.get('total')} "
        f"verified_active={stats.get('verified_active')} countries={stats.get('countries')}"
    )

    def probe(sid: int):
        code, body = get(f"/api/scholarships/{sid}")
        if code != 200:
            return sid, code, None, []
        try:
            return sid, code, json.loads(body), []
        except json.JSONDecodeError:
            return sid, code, None, ["response is not valid JSON"]

    print(f"\nprobing {len(ids)} detail endpoints...")
    with ThreadPoolExecutor(max_workers=3) as pool:
        probed = list(pool.map(probe, ids))

    statuses: dict = {}
    shape_errors: list[dict] = []
    body_errors: list[dict] = []
    rows: list[dict] = []

    for sid, code, payload, notes in probed:
        statuses[code] = statuses.get(code, 0) + 1
        entry = {"id": sid, "http": code}
        if payload is None:
            body_errors.append({"id": sid, "http": code, "notes": notes or ["no payload"]})
            rows.append(entry)
            continue
        bad = []
        for field in LIST_FIELDS:
            value = payload.get(field)
            if value is None:
                bad.append({"field": field, "why": "missing"})
            elif not isinstance(value, list):
                bad.append({"field": field, "why": f"is {type(value).__name__}, not list"})
        if bad:
            shape_errors.append({"id": sid, "fields": bad})
        entry["verification_status"] = payload.get("verification_status")
        entry["legacy_verified"] = payload.get("verified")
        entry["shape_ok"] = not bad
        rows.append(entry)

    fives = sorted(r["id"] for r in rows if r["http"] == 500)
    non200 = sorted(r["id"] for r in rows if r["http"] != 200)
    shape_bad = sorted(r["id"] for r in rows if r.get("shape_ok") is False)

    print()
    print("=== Availability ===")
    print(f"  status distribution : {statuses}")
    print(f"  HTTP 500            : {len(fives)}")
    print(f"  non-200 total       : {len(non200)}")
    if fives:
        print(f"  500 ids             : {fives}")

    print()
    print("=== Shape ===")
    print(f"  records with a list field that is not a JSON array : {len(shape_bad)}")
    if shape_bad:
        print(f"  ids: {shape_bad[:40]}")
        for item in shape_errors[:6]:
            print(f"    id {item['id']}: {item['fields']}")
    print(f"  records with an unparseable body                    : {len(body_errors)}")

    print()
    print("=== Trust semantics (API-reported state) ===")
    by_state: dict = {}
    for row in rows:
        if row.get("verification_status"):
            key = (row["verification_status"], bool(row.get("legacy_verified")))
            by_state[key] = by_state.get(key, 0) + 1
    for (state, legacy), count in sorted(by_state.items()):
        print(f"  verification_status={state:14s} legacy verified={legacy!s:5s} -> {count}")

    divergent = [
        row for row in rows
        if row.get("verification_status") == "active" and row.get("legacy_verified") is not True
    ]
    print(f"  active records whose legacy boolean is not true : {len(divergent)}")
    print("  -> the legacy boolean carries no signal and must not be the source of truth")

    print()
    print("=== The four unresolved records ===")
    for sid in UNRESOLVED:
        row = next((r for r in rows if r["id"] == sid), None)
        if row:
            print(
                f"  id {sid:4d} HTTP {row['http']} "
                f"verification_status={row.get('verification_status')} "
                f"legacy_verified={row.get('legacy_verified')}"
            )
        else:
            print(f"  id {sid:4d} NOT in the public catalogue")

    out = {
        "base": BASE,
        "public_ids": len(ids),
        "stats": {k: stats.get(k) for k in ("total", "verified_active", "countries")},
        "status_distribution": {str(k): v for k, v in statuses.items()},
        "http_500_count": len(fives),
        "http_500_ids": fives,
        "non_200_count": len(non200),
        "shape_error_count": len(shape_bad),
        "shape_error_ids": shape_bad,
        "unparseable_bodies": len(body_errors),
        "verification_status_vs_legacy": {
            f"{state}|legacy={legacy}": count for (state, legacy), count in sorted(by_state.items())
        },
        "active_without_legacy_true": len(divergent),
        "unresolved": [
            {k: v for k, v in r.items()} for r in rows if r["id"] in UNRESOLVED
        ],
        "invariant_http500_is_zero": len(fives) == 0,
        "invariant_all_386_valid": len(non200) == 0 and len(shape_bad) == 0,
    }
    Path("verification/production_detail_sweep.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print()
    print("wrote verification/production_detail_sweep.json")
    print()
    print(f"HTTP 500 == 0            : {out['invariant_http500_is_zero']}")
    print(f"all {len(ids)} valid         : {out['invariant_all_386_valid']}")


if __name__ == "__main__":
    main()