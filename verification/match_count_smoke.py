"""Live Match / Count smoke test against the deployed API.

Read-only with respect to the catalogue: `/match` and `/parse-profile` are
queries and `/counts/*` are aggregates. Nothing here writes a scholarship.

The request bodies come from the deployed contract (`MatchProfileRequest`,
`CountIntelligenceRequest`), not from guesswork. Two earlier attempts guessed the
shapes and returned 422; reporting those as "endpoint broken" would have been
wrong, so the shapes are read from the application and then verified against
production.

Every assertion reconciles rather than reading a status code, because a 200 with
an internally inconsistent payload is exactly what these contracts exist to
prevent.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://scholarzone-fwzj.vercel.app"
HEADERS = {"User-Agent": "Mozilla/5.0 ScholarZoneReleaseSmoke/1.0", "Accept": "application/json"}

PROFILE = {
    "highest_qualification": "BACHELOR",
    "intended_degree_level": "MASTER",
    "intended_field": "engineering",
    "preferred_countries": ["Germany", "Netherlands"],
    "funding_requirement": "FULL_FUNDING",
    "study_mode": "FULL_TIME",
    # The contract caps limit at 200; a larger page is a 422, not a big page.
    "limit": 200,
    "include_ineligible": True,
}

IMPOSSIBLE = {
    "highest_qualification": "OTHER",
    "intended_degree_level": "OTHER",
    "intended_field": "underwater basket weaving",
    "preferred_countries": ["Antarctica"],
    "funding_requirement": "FULL_FUNDING",
    "limit": 200,
    "include_ineligible": True,
}

checks: list[dict] = []


def call(method: str, path: str, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = dict(HEADERS)
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body[:400]
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def record(name, status, note=""):
    checks.append({"check": name, "http": status, "note": note})
    print(f"  {name:50s} HTTP {status}  {note}")


def main() -> None:
    print(f"=== target {BASE} ===")
    status, health = call("GET", "/api/health")
    revision = health.get("revision") if isinstance(health, dict) else None
    record("GET /api/health", status, f"revision={revision}")

    status, contract = call("GET", "/api/v2/counts/contract")
    record(
        "GET /api/v2/counts/contract",
        status,
        f"version={contract.get('count_contract_version') if isinstance(contract, dict) else 'n/a'}",
    )

    status, options = call("GET", "/api/scholarships/match/profile-options")
    record(
        "GET /api/scholarships/match/profile-options",
        status,
        f"{len(options) if isinstance(options, list) else len(options or {})} options",
    )

    status, parsed = call(
        "POST",
        "/api/scholarships/match/parse-profile",
        {"text": "I am a master's student in engineering looking for fully funded scholarships in Germany or the Netherlands."},
    )
    record(
        "POST /api/scholarships/match/parse-profile",
        status,
        (
            f"resolved={len(parsed.get('resolved') or [])} unresolved={len(parsed.get('unresolved') or [])}"
            if isinstance(parsed, dict)
            else ""
        ),
    )

    status, match = call("POST", "/api/scholarships/match", PROFILE)
    record("POST /api/scholarships/match", status, "synthetic: master's, engineering, DE+NL, full funding")

    out: dict = {"base": BASE, "revision": revision, "checks": checks}
    if status != 200 or not isinstance(match, dict):
        print(f"\n  no match payload to reconcile (HTTP {status})")
        Path(__file__).resolve().parent.joinpath("match_count_smoke.json").write_text(
            json.dumps(out, indent=1), encoding="utf-8"
        )
        return

    results = match.get("results") or []
    total_candidates = match.get("total_candidates")
    eligible = match.get("eligible_count")
    ineligible = match.get("ineligible_count")
    needs_verification = match.get("needs_verification_count")
    strong = match.get("strong_match_count")
    truncated = match.get("truncated")

    print("\n--- Match response ---")
    print(f"  engine_version                : {match.get('engine_version')}")
    print(f"  scoring_config_version        : {match.get('scoring_config_version')}")
    print(f"  taxonomy_version              : {match.get('taxonomy_version')}")
    print(f"  total_candidates              : {total_candidates}")
    print(f"  eligible_count                : {eligible}")
    print(f"  ineligible_count              : {ineligible}")
    print(f"  needs_verification_count      : {needs_verification}")
    print(f"  strong_match_count            : {strong}")
    print(f"  results returned              : {len(results)} (truncated={truncated})")

    print("\n--- Reconciliation ---")
    partition_sum = (eligible or 0) + (ineligible or 0) + (needs_verification or 0)
    print(f"  eligible+ineligible+needs_verification = {partition_sum}")
    print(f"  equals total_candidates               : {partition_sum == total_candidates}")

    ids = [r.get("scholarship_id") for r in results]
    print(f"  results ids distinct                 : {len(set(ids))} of {len(ids)}")

    eligibility_states: dict = {}
    for row in results:
        key = str(row.get("eligibility"))
        eligibility_states[key] = eligibility_states.get(key, 0) + 1
    print(f"  eligibility states in results         : {eligibility_states}")
    print(f"  their sum                             : {sum(eligibility_states.values())}")

    facets = match.get("facets") if isinstance(match.get("facets"), dict) else {}
    fit_bands = facets.get("fit_bands") if isinstance(facets.get("fit_bands"), dict) else {}
    confidence_bands = (
        facets.get("confidence_bands") if isinstance(facets.get("confidence_bands"), dict) else {}
    )
    if fit_bands:
        print(f"  facet fit_bands                      : {fit_bands} sum={sum(fit_bands.values())}")
    if confidence_bands:
        print(f"  facet confidence_bands               : {confidence_bands} sum={sum(confidence_bands.values())}")

    index = match.get("profile_index") if isinstance(match.get("profile_index"), dict) else {}
    strength = match.get("profile_strength") if isinstance(match.get("profile_strength"), dict) else {}
    print(f"  profile_index                        : score={index.get('score')} band={index.get('band')}")
    print(f"  profile_strength                     : score={strength.get('score')} label={strength.get('label')}")

    out.update(
        {
            "engine_version": match.get("engine_version"),
            "scoring_config_version": match.get("scoring_config_version"),
            "taxonomy_version": match.get("taxonomy_version"),
            "total_candidates": total_candidates,
            "eligible_count": eligible,
            "ineligible_count": ineligible,
            "needs_verification_count": needs_verification,
            "strong_match_count": strong,
            "results_returned": len(results),
            "truncated": truncated,
            "partition_reconciles": partition_sum == total_candidates,
            "result_ids_distinct": len(set(ids)),
            "eligibility_states": eligibility_states,
            "fit_bands": fit_bands or None,
            "confidence_bands": confidence_bands or None,
        }
    )

    # Count Intelligence must agree with Match on the same universe.
    status, intel = call("POST", "/api/v2/counts/intelligence", {"profile": PROFILE})
    note = ""
    if isinstance(intel, dict):
        u = intel.get("universes") or intel.get("universe")
        if isinstance(u, dict):
            note = f"universes={ {k: (v.get('total') if isinstance(v, dict) else v) for k, v in list(u.items())[:6]} }"
        else:
            note = f"keys={sorted(u)[:6] if u else sorted(intel)[:8]}"
        totals = {
            k: v.get("total")
            for k, v in u.items()
            if isinstance(v, dict) and "total" in v
        } if isinstance(u, dict) else {}
        if totals:
            print(f"\n--- Count Intelligence agreement ---")
            print(f"  intelligence totals                 : {totals}")
            print(f"  Match total_candidates              : {total_candidates}")
            agree = all(v == total_candidates for v in totals.values() if v is not None)
            print(f"  every intelligence universe == Match: {agree}")
            out["counts_totals"] = totals
            out["counts_agree_with_match"] = agree
    record("POST /api/v2/counts/intelligence", status, note)

    status, empty = call("POST", "/api/scholarships/match", IMPOSSIBLE)
    empty_results = (empty or {}).get("results") if isinstance(empty, dict) else []
    empty_strong = (empty or {}).get("strong_match_count") if isinstance(empty, dict) else None
    record(
        "POST /api/scholarships/match (zero-result)",
        status,
        f"strong_match_count={empty_strong} results={len(empty_results or [])} (must still answer 200)",
    )
    out["zero_result_strong_matches"] = empty_strong

    print("\nwrote verification/match_count_smoke.json")
    Path(__file__).resolve().parent.joinpath("match_count_smoke.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()