"""Fetch a candidate official page and print a compact, quotable digest.

The research pass needs many page checks without loading full page text
into the conversation each time. This prints the page title and only the
lines that carry dates, deadlines or application-status wording, so the
digest is directly quotable and small.

Usage: python research_probe.py <url> [more urls...]
"""

from __future__ import annotations

import html
import re
import sys
import urllib.request

KEYWORDS = re.compile(
    r"(deadline|apply|application|applications|open|close|closes|closing|intake|"
    r"202[5-8]|stipend|allowance|funding|covers|tuition|eligib|window|round|"
    r"scholarship|program|programme)",
    re.IGNORECASE,
)


def fetch(url: str, limit: int = 45) -> list[str]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (catalogue-research; contact: research)"}
    )
    with urllib.request.urlopen(request, timeout=50) as response:
        body = response.read(1_200_000).decode(response.headers.get_content_charset() or "utf-8", "replace")
    title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    lines: list[str] = []
    if title:
        lines.append("TITLE: " + html.unescape(re.sub(r"\s+", " ", title.group(1))).strip())
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    for chunk in re.split(r"\n|(?<=[.;!?])\s+", text):
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) < 12 or len(chunk) > 400:
            continue
        if KEYWORDS.search(chunk):
            lines.append(chunk)
        if len(lines) >= limit:
            break
    return lines


def main(urls: list[str]) -> int:
    for url in urls:
        print("=" * 20, url)
        try:
            for line in fetch(url):
                print(" ", line)
        except Exception as error:  # noqa: BLE001 - report, don't crash
            print("  FETCH FAILED:", type(error).__name__, str(error)[:160])
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1:]))
