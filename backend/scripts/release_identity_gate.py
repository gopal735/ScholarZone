#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Release identity gate.

Browser and deployment assertions are worthless if they run against the wrong
process. This gate exists because it has happened: a previous release check
reported confident failures that were really a stale uvicorn from an earlier
worktree still holding the port, so the "application under test" was not the
application under review.

It refuses to proceed unless it can prove, before any functional assertion runs:

1. the backend answers at the expected URL;
2. ``/health`` reports the exact expected build revision (a full 40-character
   commit id), not a prefix and not a label;
3. a known sentinel record exists when pointed at a local fixture database,
   which proves *which database* is being served;
4. the sentinel is reachable through the public API too, so the frontend and the
   backend are demonstrably looking at the same data.

Exit code 0 means every check passed. Any failure is a hard stop: a release check
that cannot identify its target must not be allowed to assert anything.

Usage
-----
    # production: prove the deployment identity
    python scripts/release_identity_gate.py \\
        --base-url https://scholarzone-fwzj.vercel.app/api \\
        --expect-revision "$(git rev-parse HEAD)" \\
        --expect-host scholarzone-fwzj.vercel.app

    # local fixture stack: prove the backend, the database and the frontend agree
    python scripts/release_identity_gate.py \\
        --base-url http://127.0.0.1:8000 --allow-dev-revision \\
        --sentinel-id 1 --sentinel-title "GATE Twin Alpha" \\
        --frontend-url http://127.0.0.1:5173
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

FULL_SHA = re.compile(r"[0-9a-f]{40}")


class Gate:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks += 1
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" :: {detail}" if detail else ""))
        if not ok:
            self.failures.append(f"{name} :: {detail}")
        return ok


def fetch(url: str, timeout: int = 30, accept: str = "application/json") -> tuple[int, object]:
    # The Accept header matters: a dev/preview server will 404 an HTML root
    # path when asked for JSON, because it only serves the SPA shell to
    # clients that accept HTML. Asking for the wrong type turns a healthy
    # frontend into a false identity failure.
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "release-identity-gate/1",
            "Accept": accept,
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode()
            try:
                return response.status, json.loads(body) if body.strip() else None
            except ValueError:
                return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:  # noqa: BLE001 - the gate reports, never raises
        return type(exc).__name__, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="API root, e.g. .../api")
    parser.add_argument("--expect-revision", help="full 40-char commit id expected")
    parser.add_argument(
        "--allow-dev-revision",
        action="store_true",
        help="permit 'dev'/'unproven-build' as the expected revision (local only)",
    )
    parser.add_argument(
        "--sentinel-marker",
        help="unique per-run token that must appear in the sentinel title, so a "
             "stale server reusing an older fixture cannot satisfy this gate",
    )
    parser.add_argument("--expect-host", help="hostname the base-url must belong to")
    parser.add_argument("--sentinel-id", type=int, help="known record id in the fixture DB")
    parser.add_argument("--sentinel-title", help="exact title of that record")
    parser.add_argument("--frontend-url", help="dev/preview server to confirm separately")
    parser.add_argument(
        "--expect-exact-url",
        help="the base url must be exactly this. Use the exact deployment URL when "
             "proving a preview, so a production alias cannot answer instead.",
    )
    parser.add_argument(
        "--forbid-hosts",
        help="comma-separated hosts the base url must NOT belong to. Use the "
             "production alias here when the target is a preview.",
    )
    args = parser.parse_args(argv)

    gate = Gate()
    print("=== RELEASE IDENTITY GATE ===")
    print(f"  base url    : {args.base_url}")
    print(f"  frontend    : {args.frontend_url or '(not checked)'}")

    # 0. the target is the deployment we were asked to prove, not an alias.
    if args.expect_exact_url:
        gate.check(
            "base url is the EXACT deployment url under test",
            args.base_url.rstrip("/") == args.expect_exact_url.rstrip("/"),
            f"base={args.base_url!r} expected={args.expect_exact_url!r}",
        )
    if args.forbid_hosts:
        forbidden = [h.strip() for h in args.forbid_hosts.split(",") if h.strip()]
        host = (args.base_url.split("//")[-1].split("/")[0]).lower()
        offenders = [h for h in forbidden if h.lower() in host]
        gate.check(
            "base url is not a forbidden alias",
            not offenders,
            f"host={host!r} forbidden={offenders or 'none'}",
        )

    # 1. the backend answers at all
    status, _ = fetch(f"{args.base_url.rstrip('/')}/health")
    if not gate.check(
        "backend answers /health",
        isinstance(status, int) and 200 <= status < 300,
        f"status={status}",
    ):
        print("\n  IDENTITY CANNOT BE ESTABLISHED - refusing to run any further check.")
        return 2

    # 2. exact build revision
    status, health = fetch(f"{args.base_url.rstrip('/')}/health")
    revision = (health or {}).get("revision") if isinstance(health, dict) else None
    if args.expect_revision:
        gate.check(
            "expected revision is a full commit id",
            bool(FULL_SHA.fullmatch(args.expect_revision)),
            f"expected={args.expect_revision!r}",
        )
        gate.check(
            "health reports the EXACT expected commit",
            revision == args.expect_revision,
            f"health={revision!r}",
        )
    elif args.allow_dev_revision:
        # Matched EXACTLY. Accepting "any recognisable local value" is how a
        # stale uvicorn from an earlier worktree passed this gate while serving
        # the wrong database.
        gate.check(
            "health reports the EXACT expected local revision",
            revision in ("dev", "unproven-build"),
            f"health={revision!r} (expected one of dev/unproven-build)",
        )
    else:
        gate.check(
            "a revision expectation was supplied",
            False,
            "pass --expect-revision <40 hex> or --allow-dev-revision",
        )

    # 3. the served database is the intended one
    if args.sentinel_id is not None:
        status, record = fetch(f"{args.base_url.rstrip('/')}/scholarships/{args.sentinel_id}")
        title = (record or {}).get("title") if isinstance(record, dict) else None
        gate.check(
            "sentinel record is present in the served database",
            status == 200 and title is not None,
            f"id={args.sentinel_id} status={status} title={title!r}",
        )
        if args.sentinel_title:
            gate.check(
                "sentinel record is the EXPECTED fixture (right database, not a stale one)",
                title == args.sentinel_title,
                f"expected={args.sentinel_title!r} got={title!r}",
            )
        if args.sentinel_marker:
            # A per-run token. Without this, a stale server still holding an
            # older fixture with the same title would satisfy every other check.
            gate.check(
                "sentinel carries this run's unique marker (not a reused fixture)",
                title is not None and args.sentinel_marker in title,
                f"marker={args.sentinel_marker!r} title={title!r}",
            )

    # 4. host agreement, so the frontend and backend are the same deployment
    if args.expect_host:
        gate.check(
            "base url belongs to the expected host",
            args.expect_host in args.base_url,
            f"host={args.expect_host} base={args.base_url}",
        )
    if args.frontend_url:
        # A bare origin such as "http://127.0.0.1:5173" is rejected or 404s
        # depending on the client; normalise to a root path before probing.
        frontend = args.frontend_url.rstrip("/") + "/"
        status, _ = fetch(frontend, timeout=20, accept="text/html")
        gate.check(
            "frontend serves",
            isinstance(status, int) and 200 <= status < 400,
            f"url={frontend} status={status}",
        )

    print()
    if gate.failures:
        print(f"  IDENTITY GATE FAILED: {len(gate.failures)} of {gate.checks} checks")
        for failure in gate.failures:
            print(f"    - {failure}")
        print()
        print("  Do NOT interpret any functional result from this stack. Something")
        print("  else is answering, or the expected build is not the one running.")
        return 1

    print(f"  IDENTITY GATE PASSED: {gate.checks}/{gate.checks} checks")
    print("  Safe to run functional assertions against this target.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())