"""Check that every public surface reads verification the same way.

The three trust defects already fixed were all the same mistake in three
places: a page deciding what "verified" means for itself instead of asking the
one contract. This sweep looks for that mistake again across every public
surface and every API field the frontend consumes.

It is a static check on the shipped frontend and router sources plus a live
check of the API, because a rule that only holds on one page is not a contract.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"
BASE = "https://scholarzone-fwzj.vercel.app"

#: `verified` is the legacy boolean. It is true on every record and absent on
#: none, so any expression that falls back to it - or defaults a missing value
#: to true - publishes a claim the record never made.
LEGACY_PATTERNS = [
    (r"\.verified\s*\?\?", "fallback to the legacy boolean"),
    (r"verified\s*\|\|\s*true", "defaults a missing value to verified"),
    (r"verified\s*\?\s*true\s*:\s*false", "recomputes verification from the boolean"),
    (r"scholarship\.verified\b", "reads the legacy boolean directly"),
    (r"item\.verified\b", "reads the legacy boolean directly"),
    (r"\.is_verified\b", "reads the legacy column directly from a public surface"),
]

#: The authoritative contract, which every surface must agree with.
AUTHORITATIVE = "verification_status"

SURFACES = [
    "components/ScholarshipList.jsx",
    "components/ScholarshipCard.jsx",
    "components/Navigation.jsx",
    "pages/HomePage.jsx",
    "pages/ScholarshipsPage.jsx",
    "pages/ScholarshipDetailsPage.jsx",
    "pages/ScholarshipDetailPage.jsx",
    "pages/StatsPage.jsx",
    "pages/ComparePage.jsx",
    "pages/SavedPage.jsx",
    "pages/AlertPage.jsx",
    "services/scholarshipService.js",
    "services/api.js",
]


def scan() -> list[dict]:
    findings: list[dict] = []
    for relative in SURFACES:
        path = FRONTEND / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, why in LEGACY_PATTERNS:
            for match in re.finditer(pattern, text):
                line = text[: match.start()].count("\n") + 1
                findings.append(
                    {
                        "file": relative,
                        "line": line,
                        "pattern": pattern,
                        "why": why,
                        "source_line": text.splitlines()[line - 1].strip()[:160],
                    }
                )
    return findings


def api_state() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 ScholarZoneTrustSweep/1.0", "Accept": "application/json"}

    def get(path):
        try:
            req = urllib.request.Request(f"{BASE}{path}", headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, None

    stats_status, stats = get("/api/scholarships/stats")
    list_status, listing = get("/api/scholarships?limit=100")
    out = {
        "stats_status": stats_status,
        "list_status": list_status,
        "authoritative_field": AUTHORITATIVE,
    }
    if stats:
        out["stats"] = {
            k: stats.get(k)
            for k in ("total", "verified_active", "countries", "open", "with_official_source")
        }
    if listing and listing.get("items"):
        item = listing["items"][0]
        out["list_item_keys"] = sorted(item)
        out["legacy_verified_true_on_first_page"] = sum(
            1 for r in listing["items"] if r.get("verified") is True
        )
        out["verification_status_counts_first_page"] = {
            value: sum(1 for r in listing["items"] if r.get("verification_status") == value)
            for value in sorted({r.get("verification_status") for r in listing["items"]})
        }
    return out


def main() -> None:
    findings = scan()
    print(f"public surfaces scanned      : {sum(1 for s in SURFACES if (FRONTEND / s).exists())}")
    print(f"legacy-trust findings        : {len(findings)}")
    for finding in findings:
        print(
            f"  {finding['file']}:{finding['line']} "
            f"[{finding['why']}] {finding['source_line']}"
        )
    state = api_state()
    print("api stats status             :", state["stats_status"])
    print("api stats                    :", state.get("stats"))
    print("legacy verified=true on p1   :", state.get("legacy_verified_true_on_first_page"))
    print("verification_status on p1    :", state.get("verification_status_counts_first_page"))
    (ROOT / "verification" / "trust_semantics_sweep.json").write_text(
        json.dumps({"findings": findings, "api": state}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("wrote verification/trust_semantics_sweep.json")


if __name__ == "__main__":
    main()