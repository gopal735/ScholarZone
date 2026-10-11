"""Extract the stipend wording from the official MEXT English guidelines PDF.

The 374/514 pair disagrees on the monthly stipend (143,000 vs 144,000 JPY)
and the deciding document is the English application guidelines PDF that
the merged record points at. This downloads it, extracts the text with
pypdf and prints the lines that state amounts, so the value the official
document actually publishes can be quoted.

Usage: python research_pdf.py <pdf-url> [grep-substring]
"""
from __future__ import annotations

import io
import re
import sys
import urllib.request

import pypdf


def main(args: list[str]) -> int:
    url, needle = args[0], (args[1] if len(args) > 1 else "yen|month|stipend|allowance|144|145|143")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read(20_000_000)
    reader = pypdf.PdfReader(io.BytesIO(raw))
    print(f"{len(reader.pages)} pages")
    pattern = re.compile(needle, re.I)
    hits = 0
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for line in re.split(r"\n", text):
            line = re.sub(r"\s+", " ", line).strip()
            if line and pattern.search(line):
                print(f"  p{number}: {line[:180]}")
                hits += 1
                if hits > 30:
                    return 0
    if not hits:
        print("no matching lines")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1:]))
