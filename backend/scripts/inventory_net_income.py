"""Phase 1 inventory: what net-income evidence does the corpus actually hold?

Answers, per country, the questions the net-income track has to answer before any
research starts: is there a gross figure, is there a net figure, what backs it,
what tax year, what currency and period, what status, and what break-even currently
does.

Deliberately read-only. The point of an inventory is to establish what is missing
before deciding what to go and find, and an inventory that quietly changes
something has stopped being an inventory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.country_intelligence.corpus import load_corpus  # noqa: E402
from app.services.country_intelligence.derive import (  # noqa: E402
    Derivation,
    derive_break_even,
    derive_living,
    derive_one_time_total,
    derive_total_investment,
    derive_tuition,
    find_claim,
)

#: Path fragments that count as income evidence. Matched case-insensitively
#: against the dotted claim path.
INCOME_HINTS = ("salary", "income", "wage", "earnings", "pay", "take_home", "net_")
#: Salary figures that describe an immigration threshold rather than what someone
#: earns. A Blue Card salary floor is a legal test, not an income observation, and
#: treating it as one would let break-even run on a figure nobody is paid.
THRESHOLD_HINTS = ("blue_card", "threshold", "permit", "financial_proof", "blocked")


def _is_threshold(path: str) -> bool:
    lowered = path.lower()
    return any(hint in lowered for hint in THRESHOLD_HINTS)


def income_claims(record) -> list[dict]:
    """Every income-shaped claim in one country, with its full provenance."""
    found: list[dict] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            status = node.get("value_status")
            if status and any(hint in path.lower() for hint in INCOME_HINTS):
                found.append(
                    {
                        "path": path,
                        "value": node.get("value"),
                        "currency": node.get("currency"),
                        "per": node.get("per"),
                        "basis": node.get("basis"),
                        "status": status,
                        "as_of": node.get("as_of"),
                        "freshness": node.get("freshness"),
                        "source_ids": list(node.get("source_ids") or []),
                        "note": node.get("note"),
                        "is_threshold": _is_threshold(path),
                        "formula": node.get("formula"),
                    }
                )
            for key, value in node.items():
                if key in (
                    "source_ids", "note", "formula", "previous", "conflicting",
                    "colliding_values",
                ):
                    continue
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(record.sections, "")
    return found


def break_even_state(record) -> tuple[str, str]:
    """What the calculator currently does for this country, and why."""
    tuition = derive_tuition(record.sections, "bachelor", 0.0)
    living = derive_living(record.sections, "high")
    one_time = derive_one_time_total(record.sections)
    investment = derive_total_investment(tuition, living, one_time, 2)
    net_income = find_claim(record.sections, ("career", "net_monthly_income"))
    result = derive_break_even(investment, net_income)
    if result.computed:
        return "COMPUTABLE", f"{result.value} months"
    return "REFUSED", str(result.refusal or "no income input")


def main() -> int:
    corpus = load_corpus()
    rows = []
    for record in sorted(corpus.records, key=lambda item: item.iso2):
        claims = income_claims(record)
        usable = [claim for claim in claims if not claim["is_threshold"]]
        gross = [c for c in usable if c["basis"] == "gross" and c["value"] is not None]
        net = [
            c
            for c in usable
            if c["value"] is not None
            and (c["basis"] == "net" or "net_monthly_income" in c["path"])
        ]
        derived_net = [c for c in usable if c["status"] == "DERIVED" and c["value"] is not None]
        computable, reason = break_even_state(record)
        rows.append(
            {
                "iso2": record.iso2,
                "gross_figures": len(gross),
                "net_figure": len(net),
                "net_derived": len(derived_net),
                "net_source_present": bool(net or derived_net),
                "tax_year_present": any(
                    c["as_of"] and len(str(c["as_of"])) >= 4 for c in (net or derived_net)
                ),
                "currency_present": any(c["currency"] for c in (net or derived_net)),
                "period_present": any(c["per"] for c in (net or derived_net)),
                "status": (net or derived_net or [{"status": "-"}])[0]["status"],
                "break_even": computable,
                "break_even_reason": reason,
                "threshold_claims": len(claims) - len(usable),
                "claims": usable,
            }
        )

    print(f"{'CC':3}{'GRSS':>5}{'NET':>4}{'NETDER':>7}{'TXFYR':>6}{'CUR':>5}{'PER':>5}  "
          f"{'BREAK-EVEN':<11} REASON")
    print("-" * 100)
    for row in rows:
        print(
            f"{row['iso2']:3}{row['gross_figures']:>5}{row['net_figure']:>4}"
            f"{row['net_derived']:>7}"
            f"{'Y' if row['tax_year_present'] else '-':>6}"
            f"{'Y' if row['currency_present'] else '-':>5}"
            f"{'Y' if row['period_present'] else '-':>5}  "
            f"{row['break_even']:<11} {row['break_even_reason']}"
        )
    print("-" * 100)
    print(
        f"countries with any net evidence: "
        f"{sum(1 for r in rows if r['net_source_present'])}/{len(rows)}"
    )
    print(f"break-even computable: {sum(1 for r in rows if r['break_even'] == 'COMPUTABLE')}/{len(rows)}")
    print(
        "note: Blue Card / financial-proof thresholds are excluded from the income "
        "counts above. A salary floor is a legal test, not an income observation."
    )

    out = Path(__file__).resolve().parents[2] / "NET_INCOME_BASELINE_INVENTORY.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
