"""Phase 6 named records: prove each one explicitly rather than by inference.

The sweep reports aggregates. These are the individual records the release
briefing calls out, including the two that used to answer 500 and one that is
archived, which is expected to be absent from the public universe rather than
to fail.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "https://scholarzone-fwzj.vercel.app"
LIST_FIELDS = (
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "required_documents",
    "application_method",
)

# (id, expectation, note). "active" / "needs_review" assert the verification
# state; "listed-or-reachable" asserts only that the endpoint answers, because
# the record is archived and therefore deliberately absent from the directory.
NAMED = [
    (16, "active", "ordinary verified record, previously one of the 117 failures"),
    (113, "needs_review", "UGC JRF, previously HTTP 500"),
    (140, "needs_review", "Turin, previously HTTP 500 and behind 403 official pages"),
    (466, "active", "record outside the earlier repair artifact"),
    (416, "listed-or-reachable", "archived, so absent from the directory by design"),
]


def get(path):
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"User-Agent": "Mozilla/5.0 ScholarZoneNamedSweep/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__, None


def main() -> None:
    failures = []
    print(f"{'id':>5}  {'http':>5}  {'verification_status':<20}  arrays_ok  note")
    for sid, expected, note in NAMED:
        status, payload = get(f"/api/scholarships/{sid}")
        if expected == "listed-or-reachable":
            # Archived records are excluded from the directory by
            # public_visibility_conditions, but the detail lookup is an
            # unfiltered session.get, so they stay reachable by direct URL.
            # That is pre-existing and is a visibility question, not a
            # list-shape one; it is reported rather than changed here.
            ok = status == 200
            print(
                f"{sid:>5}  {status:>5}  {str((payload or {}).get('verification_status')):<20}  "
                f"{'-':^9s}  {note} -> {'OK' if ok else 'FAIL'}"
            )
            if not ok:
                failures.append({"id": sid, "why": f"expected a response, got {status}"})
            continue

        if status != 200 or payload is None:
            failures.append({"id": sid, "why": f"HTTP {status}"})
            print(f"{sid:>5}  {status:>5}  {'-':<20}  {'-':^9s}  {note} -> FAIL")
            continue

        arrays_ok = all(isinstance(payload.get(f), list) for f in LIST_FIELDS)
        state = payload.get("verification_status")
        state_ok = state == expected
        if not arrays_ok:
            bad = [f for f in LIST_FIELDS if not isinstance(payload.get(f), list)]
            failures.append({"id": sid, "why": f"non-array list fields: {bad}"})
        if not state_ok:
            failures.append({"id": sid, "why": f"verification_status {state} != {expected}"})
        verdict = "OK" if arrays_ok and state_ok else "FAIL"
        print(
            f"{sid:>5}  {status:>5}  {str(state):<20}  {str(arrays_ok):^9s}  {note} -> {verdict}"
        )

    print(f"\nnamed-record failures: {len(failures)}")
    for failure in failures:
        print(f"  {failure}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()