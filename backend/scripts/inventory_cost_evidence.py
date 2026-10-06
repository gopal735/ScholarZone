"""Cost evidence inventory: what tuition and living-cost evidence actually exists.

Read-only. The point is to establish, before commissioning more research, which of
the seventeen countries already have a *usable* figure and which have only
sourced-nulls - because the two need completely different work, and commissioning
research for a country that is already covered wastes the pass.

Keeps the distinctions the contract insists on:

- A **published** figure outranks a computed one.
- A **visa financial proof** is a legal threshold, not what a student spends. It is
  counted separately, and never as living cost.
- Level and scope are preserved rather than collapsed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.country_intelligence.corpus import load_corpus  # noqa: E402

#: Topical fragments that count as living-cost evidence.
LIVING_HINTS = ("living", "monthly_cost", "rent", "accommodation")
#: Topical fragments that count as tuition evidence.
TUITION_HINTS = ("tuition_fees", "tuition", "study_fees")
#: Fragments that mean a legal threshold rather than a spending estimate. A visa
#: financial-proof rule is what the state requires you to show, which is a floor
#: and usually an underestimate of real life; a salary floor is a legal test. Both
#: are useful context and neither is a cost.
THRESHOLD_HINTS = (
    "financial_proof",
    "blocked_account",
    "blue_card",
    "threshold",
    "financial_capacity",
    "minimum_income",
    "proof_of_funds",
)
#: Statuses that mean the figure is computed rather than published.
_COMPUTED = {"DERIVED", "REFUSED", "UNKNOWN", "UNAVAILABLE_FOR_INGESTION"}


def _collect(sections, hints, exclude=()):
    """Every claim under a topical fragment, with the facts needed to judge it."""
    found: list[dict] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            if node.get("value_status"):
                lowered = path.lower()
                if any(hint in lowered for hint in hints) and not any(
                    bad in lowered for bad in exclude
                ):
                    found.append(
                        {
                            "path": path,
                            "value": node.get("value"),
                            "currency": node.get("currency"),
                            "per": node.get("per"),
                            "status": node.get("value_status"),
                            "as_of": node.get("as_of"),
                            "freshness": node.get("freshness"),
                            "sources": list(node.get("source_ids") or []),
                        }
                    )
            for key, value in node.items():
                if key in (
                    "source_ids", "note", "formula", "previous", "refusal",
                    "net_income_profile", "conflicting", "colliding_values",
                ):
                    continue
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(sections, "")
    return found


def main() -> int:
    corpus = load_corpus()
    rows = []
    for record in sorted(corpus.records, key=lambda item: item.iso2):
        tuition = [
            claim
            for claim in _collect(record.sections, ("tuition_fees", "tuition", "study_fees"))
            if claim["value"] is not None
            and "postgrad" not in claim["path"].lower()
        ]
        living = [
            claim
            for claim in _collect(record.sections, LIVING_HINTS, THRESHOLD_HINTS)
            if claim["value"] is not None
        ]
        thresholds = [
            claim
            for claim in _collect(record.sections, LIVING_HINTS + TUITION_HINTS, THRESHOLD_HINTS)
            if claim["value"] is not None
        ]

        def summarise(claims):
            published = [c for c in claims if c["status"] not in _COMPUTED]
            return {
                "total": len(claims),
                "published": len(published),
                "estimate": len([c for c in claims if c["status"] == "ESTIMATE"]),
                "computed_or_unknown": len([c for c in claims if c["status"] in _COMPUTED]),
            }

        rows.append(
            {
                "iso2": record.iso2,
                "tuition": summarise(tuition),
                "living": summarise(living),
                "thresholds": len(thresholds),
                "tuition_claims": tuition,
                "living_claims": living,
                "sources": len(record.sources),
                "gaps": len(record.gaps),
            }
        )

    print(f"{'CC':3} {'TUIT':>5}{'tu_publ':>9}{'LIV':>5}{'liv_publ':>9}{'THRESH':>8}{'SRC':>5}{'GAPS':>6}")
    print("-" * 60)
    for row in rows:
        print(
            f"{row['iso2']:3} {row['tuition']['total']:>5}{row['tuition']['published']:>9}"
            f"{row['living']['total']:>5}{row['living']['published']:>9}"
            f"{row['thresholds']:>8}{row['sources']:>5}{row['gaps']:>6}"
        )
    print("-" * 60)
    print(
        f"countries with a PUBLISHED tuition figure: "
        f"{sum(1 for r in rows if r['tuition']['published'])}/17"
    )
    print(
        f"countries with a PUBLISHED living-cost figure: "
        f"{sum(1 for r in rows if r['living']['published'])}/17"
    )
    out = Path(__file__).resolve().parents[2] / "COST_EVIDENCE_BASELINE_INVENTORY.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())