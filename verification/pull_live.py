"""Pull the live public catalogue and classify the authoritative verification state.

Read-only. The public API is the same read path the frontend uses, so this is the
public universe, not a private view of it.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://scholarzone-fwzj.vercel.app"
OUT = Path(__file__).resolve().parent / "live_catalogue.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ScholarZoneVerificationAudit/1.0",
    "Accept": "application/json",
}


def get_json(url: str, attempts: int = 4):
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"failed {url}: {last}")


def main() -> None:
    stats = get_json(f"{BASE}/api/scholarships/stats")
    total = stats["total"]
    print("stats:", json.dumps(stats))

    items: list[dict] = []
    seen: set[int] = set()
    limit = 100
    page = 1
    while len(seen) < total:
        payload = get_json(f"{BASE}/api/scholarships?limit={limit}&page={page}")
        batch = payload.get("items") or []
        if not batch:
            break
        for row in batch:
            if row["id"] not in seen:
                seen.add(row["id"])
                items.append(row)
        print(f"page {page}: +{len(batch)} (have {len(seen)})")
        page += 1
        if page > 20:
            break

    items.sort(key=lambda r: r["id"])
    OUT.write_text(
        json.dumps(
            {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "stats": stats, "items": items},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print("fetched", len(items), "->", OUT.name)

    print("\nverification_status:", dict(Counter(r.get("verification_status") for r in items)))
    print("is_verified(legacy `verified`):", dict(Counter(r.get("verified") for r in items)))
    print("status:", dict(Counter(r.get("status") for r in items)))
    print("image_kind:", dict(Counter(r.get("image_kind") for r in items)))
    print("missing source_url:", sum(1 for r in items if not r.get("source_url")))

    unresolved = [r for r in items if r.get("verification_status") != "active"]
    print(f"\nunresolved: {len(unresolved)}")
    for r in unresolved:
        print(
            f"  {r['id']:>4}  {r.get('verification_status'):<12} "
            f"{(r.get('name') or r.get('title') or '')[:64]:<64} "
            f"{(r.get('source_url') or '(none)')[:80]}"
        )


if __name__ == "__main__":
    main()