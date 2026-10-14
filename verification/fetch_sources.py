"""Bounded, cached official-source fetcher for the verification audit.

Reuses the application's own fetcher so the audit sees exactly what the
verification pipeline would see. Adds only what a research pass needs: an
on-disk cache, bounded retries with backoff, and a plain-text rendering of the
page for evidence extraction.

A fetch failure is recorded as a fetch failure. It is never evidence about the
scholarship.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.official_source_fetcher import (  # noqa: E402
    clear_official_source_cache,
    fetch_official_source,
)

HERE = Path(__file__).resolve().parent
CACHE = HERE / "fetch_cache.json"
TEXTDIR = HERE / "fetch_text"
REPORT = HERE / "fetch_report.json"

_TAG = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK = re.compile(r"\n{3,}")


def to_text(html: str) -> str:
    body = _TAG.sub(" ", html)
    body = _ANY_TAG.sub("\n", body)
    body = (
        body.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&rsquo;", "'")
        .replace("&ndash;", "-")
        .replace("&mdash;", "-")
    )
    lines = [_WS.sub(" ", ln).strip() for ln in body.split("\n")]
    return _BLANK.sub("\n\n", "\n".join(ln for ln in lines if ln)).strip()


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def fetch(url: str, retries: int = 2, force: bool = False) -> dict:
    cache = load_cache()
    if not force and url in cache:
        return cache[url]
    result = None
    for attempt in range(retries + 1):
        result = fetch_official_source(url)
        if result.success:
            break
        if result.error_type in ("not_found", "invalid_url"):
            break
        time.sleep(1.5 * (attempt + 1))
    clear_official_source_cache()
    entry = {
        "url": url,
        "success": result.success,
        "status_code": result.status_code,
        "final_url": result.final_url,
        "error_type": result.error_type,
        "error_reason": result.error_reason,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if result.success and result.content:
        text = to_text(result.content)
        digest = hashlib.sha256(result.content.encode("utf-8", "replace")).hexdigest()[:16]
        entry["text_sha256_16"] = digest
        entry["text_chars"] = len(text)
        TEXTDIR.mkdir(exist_ok=True)
        (TEXTDIR / f"{digest}.txt").write_text(text, encoding="utf-8")
        entry["text_file"] = f"{digest}.txt"
    cache[url] = entry
    save_cache(cache)
    return entry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()

    urls = list(args.urls)
    if args.file:
        urls += [ln.strip() for ln in Path(args.file).read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not urls:
        ap.error("no urls")

    out = []
    for url in urls:
        e = fetch(url, retries=args.retries, force=args.force)
        out.append(e)
        flag = "OK " if e["success"] else "ERR"
        print(
            f"{flag} {e['status_code']} {url}"
            + (f"  -> {e['final_url']}" if e["final_url"] and e["final_url"] != url else "")
            + (f"  [{e['error_type']}] {e['error_reason']}" if not e["success"] else f"  ({e.get('text_chars')} chars)"),
            flush=True,
        )

    REPORT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()