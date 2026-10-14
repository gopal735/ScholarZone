"""Fetch the full stored record for every public id, once, with a local cache.

Read-only against the deployed API. The detail endpoint is not usable for this
(it 500s on at least one record), so the debug raw projection is used instead;
it is the same rows the public list is built from.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://scholarzone-fwzj.vercel.app"
HERE = Path(__file__).resolve().parent
LIST = HERE / "live_catalogue.json"
RAW = HERE / "live_raw.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ScholarZoneVerificationAudit/1.0",
    "Accept": "application/json",
}
WORKERS = 6


def fetch_one(sid: int) -> tuple[int, dict | None, str | None]:
    url = f"{BASE}/api/scholarships/debug/raw/{sid}"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as resp:
                return sid, json.loads(resp.read().decode("utf-8")), None
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503):
                time.sleep(1.0 * (attempt + 1))
                continue
            return sid, None, f"http_{exc.code}"
        except Exception as exc:  # noqa: BLE001
            time.sleep(1.0 * (attempt + 1))
            last = f"{type(exc).__name__}: {exc}"
    return sid, None, last


def main() -> None:
    ids = [r["id"] for r in json.loads(LIST.read_text(encoding="utf-8"))["items"]]
    print("ids:", len(ids))

    cache: dict[int, dict] = {}
    if RAW.exists():
        cache = {int(k): v for k, v in json.loads(RAW.read_text(encoding="utf-8")).items()}
        print("cache hit:", len(cache))

    todo = [i for i in ids if i not in cache]
    failures: dict[str, list[int]] = {}
    if todo:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            done = 0
            for sid, row, err in pool.map(fetch_one, todo):
                done += 1
                if row is not None:
                    cache[sid] = row
                else:
                    failures.setdefault(err or "unknown", []).append(sid)
                if done % 50 == 0:
                    print(f"  {done}/{len(todo)} fetched, cache={len(cache)}")
                    RAW.write_text(
                        json.dumps({str(k): v for k, v in cache.items()}, ensure_ascii=False),
                        encoding="utf-8",
                    )

    RAW.write_text(
        json.dumps({str(k): v for k, v in sorted(cache.items())}, ensure_ascii=False),
        encoding="utf-8",
    )
    print("total records:", len(cache), "of", len(ids))
    for reason, bad in failures.items():
        print("  FAILED", reason, bad)


if __name__ == "__main__":
    main()