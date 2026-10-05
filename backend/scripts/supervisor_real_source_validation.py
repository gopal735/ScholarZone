"""Bounded, read-only validation of the source taxonomy against real public pages.

Three real institutional URLs, one request each through the normal polite path,
classified with the production functions. Nothing is written to any database and
no professor is stored: the point is to check that the taxonomy matches reality,
not to populate anything.

A failure to obtain a professor from a real site is recorded as inconclusive. It
is never, under any circumstance here, evidence that the institution employs
nobody.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, ".")

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services import supervisor_discovery as worker  # noqa: E402
from app.services.supervisor_jsdetect import classify_shell  # noqa: E402
from app.services.supervisor_source import detect_access_barrier  # noqa: E402

#: One expected-SSR directory, one expected client-side directory, one expected
#: login wall. Chosen because they are the three shapes the taxonomy must tell
#: apart, and because they were already observed read-only in an earlier phase.
TARGETS = [
    ("expected SSR directory", "https://www.cs.cmu.edu/people/", "should be readable over HTTP"),
    ("expected client-side directory", "https://adelaide.edu.au/people/", "likely a JavaScript shell"),
    ("expected login wall", "https://search.msu.edu/people/", "known to require sign-in"),
]


def main() -> None:
    print("=" * 78)
    print("BOUNDED REAL-SOURCE VALIDATION (read-only, no persistence)")
    print("=" * 78)
    for label, url, expectation in TARGETS:
        print(f"\n{label}")
        print(f"  url        : {url}")
        print(f"  expectation: {expectation}")

        started = time.monotonic()
        page = worker.polite_fetch(url)
        elapsed = int((time.monotonic() - started) * 1000)
        host = (url.split("/")[2])

        if page is None or not getattr(page, "success", True):
            diagnostic = worker.fetch_official_source(url)
            print(f"  reached    : False  ({diagnostic.error_type}/{diagnostic.status_code})")
            print(f"  robots     : {worker._robots_allows(url)}")
            print("  class      : SOURCE_BLOCKED (inaccessible; not a negative)")
            continue

        html = page.content or ""
        barrier = detect_access_barrier(html)
        shell = classify_shell(html)

        print(f"  reached    : True  ({page.status_code}, {len(html)} bytes, {elapsed}ms)")
        print(f"  barrier    : {barrier or 'none'}")
        print(f"  shell      : {shell.is_shell}  signals={shell.signals or '-'}")
        print(f"  empty doc  : {shell.empty_document}")

        if barrier:
            kind = barrier[0]
            state = "SOURCE_BLOCKED" if kind != "login_required" else "SOURCE_BLOCKED (login)"
            print(f"  class      : {state} — not attempted, no credential used")
        elif shell.needs_more_than_static:
            print("  class      : SOURCE_REQUIRES_RENDERING — inconclusive, NOT a negative")
            print("               (this run performs no browser work against live sites)")
        else:
            candidates = worker.extract_faculty_candidates(html, url, host)
            evidenced = [c for c in candidates if c.has_role_evidence]
            print(f"  class      : statically readable; candidates={len(candidates)} "
                  f"with academic-role evidence={len(evidenced)}")
            for candidate in evidenced[:3]:
                print(f"               - {candidate.name} ({candidate.role})")

    print()
    print("=" * 78)
    print("No professor was stored. No database was written. No login was attempted.")
    print("=" * 78)


if __name__ == "__main__":
    main()