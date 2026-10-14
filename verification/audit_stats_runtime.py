"""Phase 2: collect fresh live responses. No earlier artifact is trusted.

The 445 figure came from a workflow artifact captured before the last two
deployments. Everything here is fetched now, with cache-busting headers, and
each number is printed next to the response it came from.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

HOSTS = ("https://scholarzone-fwzj.vercel.app",)
HEADERS = {
    "User-Agent": "Mozilla/5.0 ScholarZoneContractAudit/1.0",
    "Accept": "application/json",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "X-Cache-Bypass": "1",
}

STATS_FIELDS = (
    "total",
    "with_image",
    "with_official_source",
    "verified_active",
    "open",
    "upcoming",
    "closed",
    "countries",
    "fully_funded",
)


def get(host, path):
    req = urllib.request.Request(host + path, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, dict(resp.headers), json.loads(raw)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), None
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__, {}, None


def main() -> None:
    for host in HOSTS:
        print(f"=== {host} ===")
        status, headers, health = get(host, "/api/health")
        revision = (health or {}).get("revision")
        print(f"/api/health -> {status}  revision={revision}")
        served = headers.get("X-Vercel-Id") or headers.get("X-Request-Id") or "-"
        print(f"  edge id: {served}")
        print()

        # Two independent fetches, to separate a live value from a cached one.
        for attempt in (1, 2):
            status, headers, stats = get(host, f"/api/scholarships/stats?audit={attempt}")
            print(f"/api/scholarships/stats (attempt {attempt}) -> {status}")
            if stats is None:
                continue
            for field in STATS_FIELDS:
                if field in stats:
                    print(f"    {field:22s} = {stats[field]}")
            extra = sorted(set(stats) - set(STATS_FIELDS))
            if extra and attempt == 1:
                print(f"    (other keys present: {extra})")
            total = stats.get("total")
            offenders = [
                (f, stats[f])
                for f in STATS_FIELDS
                if f != "total" and isinstance(stats.get(f), int) and total
                and stats[f] > total
            ]
            print(f"    -> fields exceeding total: {offenders if offenders else 'none'}")
            cache = headers.get("X-Vercel-Cache") or headers.get("Age") or "-"
            print(f"    cache header: {cache}")
            print()

        # The directory's own count, for comparison with stats.total.
        seen = []
        for page in range(1, 6):
            status, _, listing = get(host, f"/api/scholarships?limit=100&page={page}&audit=1")
            if status != 200 or not listing:
                break
            items = listing.get("items", [])
            if not items:
                break
            seen.extend(r["id"] for r in items)
        print(f"/api/scholarships -> enumerated {len(set(seen))} distinct ids")
        print()


if __name__ == "__main__":
    main()